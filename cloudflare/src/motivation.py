"""积分、成就和奖励兑换；相关余额写入在 D1 批处理中原子执行。"""

import json
from fastapi import APIRouter, HTTPException, Query, Request
from database import Database
from analytics import now

router=APIRouter(prefix='/api')


async def balance_row(db):
    """读取默认用户余额，不重复初始化历史数据。"""
    row=await db.first('SELECT * FROM star_balance WHERE user_id=1 AND deleted=0')
    if row is None:
        await db.run('INSERT INTO star_balance(user_id,balance) VALUES(1,0) ON CONFLICT(user_id) DO NOTHING')
        row=await db.first('SELECT * FROM star_balance WHERE user_id=1 AND deleted=0')
    return row


async def adjust(db,delta,reason,code='manual_adjustment'):
    """原子更新余额和积分流水，负余额通过事务内检查拒绝。"""
    await balance_row(db)
    stamp=now().isoformat(' ')
    statements=[('UPDATE write_guard SET revision=CASE WHEN (SELECT balance FROM star_balance WHERE user_id=1 AND deleted=0)+?>=0 THEN revision+1 ELSE NULL END WHERE id=1',(delta,)),
                ('UPDATE star_balance SET balance=balance+?,updated_at=? WHERE user_id=1 AND deleted=0',(delta,stamp)),
                ('INSERT INTO star_record(user_id,action_code,star_delta,balance_after,reason,deleted,created_at) SELECT 1,?,?,balance,?,0,? FROM star_balance WHERE user_id=1 AND deleted=0',(code,delta,reason,stamp))]
    try:
        result=await db.batch(statements)
    except Exception:
        raise HTTPException(400,'积分不足或积分更新失败，请刷新后重试')
    record_id=result[-1]['meta']['last_row_id']
    record=await db.first('SELECT balance_after FROM star_record WHERE id=?',(record_id,))
    return {'success':True,'new_balance':record['balance_after'],'delta':delta,'record_id':record_id}


@router.get('/stars/balance')
async def balance(request: Request):
    """读取积分余额。"""
    return {'balance':(await balance_row(Database(request.scope['env'].DB)))['balance']}


@router.get('/stars/records')
async def records(request: Request,skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200)):
    """分页读取未删除积分流水。"""
    db=Database(request.scope['env'].DB)
    count=await db.first('SELECT COUNT(*) AS total FROM star_record WHERE deleted=0')
    return {'total':count['total'],'items':await db.all('SELECT * FROM star_record WHERE deleted=0 ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',(limit,skip))}


@router.post('/stars/adjust')
async def manual(request: Request):
    """校验后手动调整积分。"""
    payload=await request.json()
    if type(payload.get('delta')) is not int or payload['delta']==0 or not isinstance(payload.get('reason'),str) or not 1<=len(payload['reason'].strip())<=200:
        raise HTTPException(422,'请输入非零积分和有效原因')
    return await adjust(Database(request.scope['env'].DB),payload['delta'],payload['reason'].strip())


@router.get('/achievements/progress')
async def progress(request: Request):
    """读取保留的成就进度与定义。"""
    db=Database(request.scope['env'].DB)
    rows=await db.all('SELECT p.* FROM achievement_progress p JOIN achievement a ON a.id=p.achievement_id WHERE p.deleted=0 AND p.user_id=1 AND a.deleted=0')
    for row in rows:
        row['is_unlocked']=bool(row['is_unlocked'])
        row['achievement']=await db.first('SELECT * FROM achievement WHERE id=? AND deleted=0',(row['achievement_id'],))
    return rows


async def unlock(db,achievement,count):
    """按原等级前置条件更新进度，解锁与积分发放在一个事务中完成。"""
    old=await db.first('SELECT * FROM achievement_progress WHERE deleted=0 AND user_id=1 AND achievement_id=?',(achievement['id'],))
    if old is None:
        await db.run('INSERT INTO achievement_progress(user_id,achievement_id,current_count,is_unlocked) VALUES(1,?,0,0) ON CONFLICT(user_id,achievement_id) DO NOTHING',(achievement['id'],))
        old=await db.first('SELECT * FROM achievement_progress WHERE deleted=0 AND user_id=1 AND achievement_id=?',(achievement['id'],))
    if old['is_unlocked']:
        return None
    previous=await db.first('SELECT p.is_unlocked FROM achievement a LEFT JOIN achievement_progress p ON p.achievement_id=a.id AND p.user_id=1 WHERE a.code=? AND a.level=? AND a.deleted=0',(achievement['code'],achievement['level']-1)) if achievement['level']>1 else None
    eligible=not previous or previous['is_unlocked']
    if count<achievement['trigger_count'] or not eligible:
        await db.run('UPDATE achievement_progress SET current_count=? WHERE id=? AND is_unlocked=0',(count,old['id']))
        return None
    stamp=now().isoformat(' ')
    amount=achievement['reward_stars'] or 0
    await balance_row(db)
    statements=[('UPDATE write_guard SET revision=CASE WHEN EXISTS(SELECT 1 FROM achievement_progress WHERE id=? AND is_unlocked=0) THEN revision+1 ELSE NULL END WHERE id=1',(old['id'],)),('UPDATE achievement_progress SET is_unlocked=1,current_count=?,unlocked_at=? WHERE id=?',(count,stamp,old['id']))]
    if amount:
        statements += [('UPDATE star_balance SET balance=balance+?,updated_at=? WHERE user_id=1 AND deleted=0',(amount,stamp)),('INSERT INTO star_record(user_id,action_code,star_delta,balance_after,reason,deleted,created_at) SELECT 1,\'reward\',?,balance,?,0,? FROM star_balance WHERE user_id=1 AND deleted=0',(amount,'成就奖励：'+achievement['name']+' Lv'+str(achievement['level']),stamp))]
    try:
        await db.batch(statements)
    except Exception:
        return None
    return {'achievement_id':achievement['id'],'name':achievement['name'],'level':achievement['level'],'reward_stars':amount}


async def trigger(db,code,reason=None):
    """按配置触发积分，并检查行为累计与连续学习成就。"""
    action=await db.first('SELECT * FROM star_action WHERE code=? AND enabled=1 AND deleted=0',(code,))
    if not action:
        raise HTTPException(404,'行为不存在或已禁用')
    result=await adjust(db,action['star_value'],reason or action['name'],code)
    achievements=await db.all('SELECT * FROM achievement WHERE trigger_action=? AND is_active=1 AND deleted=0 ORDER BY level',(code,))
    if code in ('review_word','review_practice_set'):
        table='word' if code=='review_word' else 'practice_set'
        count=(await db.first('SELECT COALESCE(SUM(review_count),0) AS count FROM '+table+' WHERE deleted=0'))['count']
    else:
        count=(await db.first('SELECT COUNT(*) AS count FROM star_record WHERE user_id=1 AND action_code=? AND deleted=0',(code,)))['count']
    unlocked=[]
    for achievement in achievements:
        item=await unlock(db,achievement,count)
        if item: unlocked.append(item)
    if code=='review_practice_set':
        dates=await db.all('SELECT DISTINCT date(created_at) AS date FROM star_record WHERE user_id=1 AND action_code=\'review_practice_set\' AND deleted=0 ORDER BY date DESC LIMIT 31')
        days={row['date'] for row in dates}
        from datetime import timedelta
        consecutive=0
        for index in range(30):
            if (now()-timedelta(days=index)).strftime('%Y-%m-%d') not in days: break
            consecutive+=1
        for achievement in await db.all('SELECT * FROM achievement WHERE code=\'continuous_learning\' AND deleted=0 ORDER BY level'):
            item=await unlock(db,achievement,consecutive)
            if item: unlocked.append(item)
    return {'star_delta':action['star_value'],'new_balance':(await balance_row(db))['balance'],'unlocked_achievements':unlocked}


@router.post('/motivation/trigger/review_word_accuracy')
async def word_accuracy(request: Request,total_count:int,correct_count:int,reason:str|None=None):
    """累计达到单词正确率要求的场次。"""
    db=Database(request.scope['env'].DB)
    config=await db.first('SELECT c.* FROM achievement_config c JOIN achievement a ON a.id=c.achievement_id WHERE a.code=\'word_accuracy\' AND a.deleted=0 LIMIT 1')
    accuracy=correct_count/total_count*100 if total_count>0 else 0
    if total_count<(config['min_words'] if config else 10) or accuracy<(config['min_accuracy'] if config else 90):
        return {'unlocked':False,'message':'未达成条件'}
    target=await db.first('SELECT a.*,COALESCE(p.current_count,0) AS current_count FROM achievement a LEFT JOIN achievement_progress p ON p.achievement_id=a.id AND p.user_id=1 WHERE a.code=\'word_accuracy\' AND a.deleted=0 AND COALESCE(p.is_unlocked,0)=0 ORDER BY a.level LIMIT 1')
    if not target: return {'unlocked':False,'message':'所有等级已解锁'}
    count=target['current_count']+1
    result=await unlock(db,target,count)
    return {'unlocked':bool(result),'unlocked_achievements':[result] if result else [],'progress':{'level':target['level'],'current_count':count,'trigger_count':target['trigger_count']},'accuracy':accuracy,'total_count':total_count,'correct_count':correct_count}


@router.post('/motivation/trigger/{action_code}')
async def trigger_endpoint(action_code:str,request:Request,reason:str|None=None):
    """触发配置的激励行为。"""
    return await trigger(Database(request.scope['env'].DB),action_code,reason)


@router.get('/motivation/overview')
async def overview(request:Request):
    """读取真实余额、成就和当日积分。"""
    db=Database(request.scope['env'].DB)
    counts=await db.first('SELECT (SELECT COUNT(*) FROM achievement WHERE deleted=0) AS achievement_total,(SELECT COUNT(*) FROM achievement_progress p JOIN achievement a ON a.id=p.achievement_id WHERE p.user_id=1 AND p.is_unlocked=1 AND a.deleted=0) AS achievement_unlocked,(SELECT COUNT(*) FROM reward WHERE deleted=0 AND is_active=1) AS rewards_available')
    today=await db.first('SELECT COALESCE(SUM(star_delta),0) AS total FROM star_record WHERE user_id=1 AND deleted=0 AND created_at>=?',(now().replace(hour=0,minute=0,second=0,microsecond=0).isoformat(' '),))
    return {'balance':(await balance_row(db))['balance'],**counts,'today_stars':today['total']}


@router.get('/rewards/redemptions')
async def redemptions(request:Request):
    """读取兑换历史及奖励详情。"""
    db=Database(request.scope['env'].DB)
    rows=await db.all('SELECT * FROM redemption WHERE deleted=0 AND user_id=1 ORDER BY redeemed_at DESC LIMIT 50')
    for row in rows: row['reward']=await db.first('SELECT * FROM reward WHERE id=? AND deleted=0',(row['reward_id'],))
    return rows


@router.post('/rewards/{reward_id}/redeem')
async def redeem(reward_id:int,request:Request):
    """原子检查余额与库存，扣积分并保存兑换和流水。"""
    db=Database(request.scope['env'].DB)
    reward=await db.first('SELECT * FROM reward WHERE id=? AND deleted=0 AND is_active=1',(reward_id,))
    if not reward: raise HTTPException(404,'奖励不存在或已下架')
    await balance_row(db)
    stamp=now().isoformat(' ')
    try:
        await db.batch([('UPDATE write_guard SET revision=CASE WHEN (SELECT balance FROM star_balance WHERE user_id=1 AND deleted=0)>=? AND EXISTS(SELECT 1 FROM reward WHERE id=? AND is_active=1 AND deleted=0 AND (remaining_stock=-1 OR remaining_stock>0)) THEN revision+1 ELSE NULL END WHERE id=1',(reward['cost_stars'],reward_id)),('UPDATE star_balance SET balance=balance-?,updated_at=? WHERE user_id=1',(reward['cost_stars'],stamp)),('UPDATE reward SET remaining_stock=CASE WHEN remaining_stock>0 THEN remaining_stock-1 ELSE remaining_stock END WHERE id=?',(reward_id,)),('INSERT INTO star_record(user_id,action_code,star_delta,balance_after,reason,deleted,created_at) SELECT 1,\'redeem\',?,balance,?,0,? FROM star_balance WHERE user_id=1 AND deleted=0',(-reward['cost_stars'],'兑换：'+reward['name'],stamp)),('INSERT INTO redemption(user_id,reward_id,star_cost,redeemed_at) VALUES(1,?,?,?)',(reward_id,reward['cost_stars'],stamp))])
    except Exception:
        raise HTTPException(400,'积分或库存不足，请刷新后重试')
    return {'success':True,'new_balance':(await balance_row(db))['balance'],'reward_name':reward['name']}
