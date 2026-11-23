"""积分、成就和奖励兑换；相关余额写入在 D1 批处理中原子执行。

余额、流水、兑换、成就进度、奖品都按学生分（以 student_id 为准）；旧列 user_id 写成家庭编号，不再用来查询。
加星规则 star_action 和成就定义 achievement 是全站共用目录。
函数里的 owner 是登录身份字典（至少有 user_id、student_id），由调用方用 current_identity(request) 取得。
"""

from fastapi import APIRouter, HTTPException, Query, Request
from database import Database
from analytics import now
from identity import current_identity

router=APIRouter(prefix='/api')


async def balance_row(db, owner):
    """读取这个学生的余额行，没有就建一行（余额 0）。"""
    sid=owner['student_id']
    row=await db.first('SELECT * FROM star_balance WHERE student_id=? AND deleted=0',(sid,))
    if row is None:
        await db.run('INSERT INTO star_balance(user_id,student_id,balance) VALUES(?,?,0) '
                     'ON CONFLICT(student_id) WHERE deleted=0 DO NOTHING',(owner['user_id'],sid))
        row=await db.first('SELECT * FROM star_balance WHERE student_id=? AND deleted=0',(sid,))
    return row


async def adjust(db,owner,delta,reason,code='manual_adjustment'):
    """原子更新余额和积分流水，负余额通过事务内检查拒绝。"""
    await balance_row(db,owner)
    sid=owner['student_id']
    stamp=now().isoformat(' ')
    statements=[('UPDATE write_guard SET revision=CASE WHEN (SELECT balance FROM star_balance WHERE student_id=? AND deleted=0)+?>=0 THEN revision+1 ELSE NULL END WHERE id=1',(sid,delta)),
                ('UPDATE star_balance SET balance=balance+?,updated_at=? WHERE student_id=? AND deleted=0',(delta,stamp,sid)),
                ('INSERT INTO star_record(user_id,student_id,action_code,star_delta,balance_after,reason,deleted,created_at) '
                 'SELECT ?,student_id,?,?,balance,?,0,? FROM star_balance WHERE student_id=? AND deleted=0',
                 (owner['user_id'],code,delta,reason,stamp,sid))]
    try:
        result=await db.batch(statements)
    except Exception:
        raise HTTPException(400,'积分不足或积分更新失败，请刷新后重试')
    record_id=result[-1]['meta']['last_row_id']
    record=await db.first('SELECT balance_after FROM star_record WHERE id=? AND student_id=?',(record_id,sid))
    return {'success':True,'new_balance':record['balance_after'],'delta':delta,'record_id':record_id}


@router.get('/stars/balance')
async def balance(request: Request):
    """读取积分余额。"""
    return {'balance':(await balance_row(Database(request.scope['env'].DB),current_identity(request)))['balance']}


@router.get('/stars/records')
async def records(request: Request,skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200)):
    """分页读取未删除积分流水。"""
    db=Database(request.scope['env'].DB)
    sid=current_identity(request)['student_id']
    count=await db.first('SELECT COUNT(*) AS total FROM star_record WHERE deleted=0 AND student_id=?',(sid,))
    return {'total':count['total'],'items':await db.all('SELECT * FROM star_record WHERE deleted=0 AND student_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',(sid,limit,skip))}


@router.post('/stars/adjust')
async def manual(request: Request):
    """校验后手动调整积分。"""
    payload=await request.json()
    if type(payload.get('delta')) is not int or payload['delta']==0 or not isinstance(payload.get('reason'),str) or not 1<=len(payload['reason'].strip())<=200:
        raise HTTPException(422,'请输入非零积分和有效原因')
    return await adjust(Database(request.scope['env'].DB),current_identity(request),payload['delta'],payload['reason'].strip())


@router.get('/achievements/progress')
async def progress(request: Request):
    """读取保留的成就进度与定义。"""
    db=Database(request.scope['env'].DB)
    rows=await db.all('SELECT p.* FROM achievement_progress p JOIN achievement a ON a.id=p.achievement_id WHERE p.deleted=0 AND p.student_id=? AND a.deleted=0',
                      (current_identity(request)['student_id'],))
    for row in rows:
        row['is_unlocked']=bool(row['is_unlocked'])
        row['achievement']=await db.first('SELECT * FROM achievement WHERE id=? AND deleted=0',(row['achievement_id'],))
    return rows


async def unlock(db,owner,achievement,count):
    """按原等级前置条件更新进度，解锁与积分发放在一个事务中完成。"""
    sid=owner['student_id']
    old=await db.first('SELECT * FROM achievement_progress WHERE deleted=0 AND student_id=? AND achievement_id=?',(sid,achievement['id']))
    if old is None:
        await db.run('INSERT INTO achievement_progress(user_id,student_id,achievement_id,current_count,is_unlocked) VALUES(?,?,?,0,0) '
                     'ON CONFLICT(student_id,achievement_id) WHERE deleted=0 DO NOTHING',(owner['user_id'],sid,achievement['id']))
        old=await db.first('SELECT * FROM achievement_progress WHERE deleted=0 AND student_id=? AND achievement_id=?',(sid,achievement['id']))
    if old['is_unlocked']:
        return None
    previous=await db.first('SELECT p.is_unlocked FROM achievement a LEFT JOIN achievement_progress p ON p.achievement_id=a.id AND p.student_id=? AND p.deleted=0 WHERE a.code=? AND a.level=? AND a.deleted=0',(sid,achievement['code'],achievement['level']-1)) if achievement['level']>1 else None
    eligible=not previous or previous['is_unlocked']
    if count<achievement['trigger_count'] or not eligible:
        await db.run('UPDATE achievement_progress SET current_count=? WHERE id=? AND student_id=? AND is_unlocked=0',(count,old['id'],sid))
        return None
    stamp=now().isoformat(' ')
    amount=achievement['reward_stars'] or 0
    await balance_row(db,owner)
    statements=[('UPDATE write_guard SET revision=CASE WHEN EXISTS(SELECT 1 FROM achievement_progress WHERE id=? AND student_id=? AND is_unlocked=0) THEN revision+1 ELSE NULL END WHERE id=1',(old['id'],sid)),
                ('UPDATE achievement_progress SET is_unlocked=1,current_count=?,unlocked_at=? WHERE id=? AND student_id=?',(count,stamp,old['id'],sid))]
    if amount:
        statements += [('UPDATE star_balance SET balance=balance+?,updated_at=? WHERE student_id=? AND deleted=0',(amount,stamp,sid)),
                       ('INSERT INTO star_record(user_id,student_id,action_code,star_delta,balance_after,reason,deleted,created_at) '
                        'SELECT ?,student_id,\'reward\',?,balance,?,0,? FROM star_balance WHERE student_id=? AND deleted=0',
                        (owner['user_id'],amount,'成就奖励：'+achievement['name']+' Lv'+str(achievement['level']),stamp,sid))]
    try:
        await db.batch(statements)
    except Exception:
        return None
    return {'achievement_id':achievement['id'],'name':achievement['name'],'level':achievement['level'],'reward_stars':amount}


async def trigger(db,owner,code,reason=None):
    """按配置触发积分，并检查行为累计与连续学习成就（只算这个学生的）。"""
    sid=owner['student_id']
    action=await db.first('SELECT * FROM star_action WHERE code=? AND enabled=1 AND deleted=0',(code,))
    if not action:
        raise HTTPException(404,'行为不存在或已禁用')
    result=await adjust(db,owner,action['star_value'],reason or action['name'],code)
    achievements=await db.all('SELECT * FROM achievement WHERE trigger_action=? AND is_active=1 AND deleted=0 ORDER BY level',(code,))
    if code in ('review_word','review_practice_set'):
        table='word' if code=='review_word' else 'practice_set'
        count=(await db.first('SELECT COALESCE(SUM(review_count),0) AS count FROM '+table+' WHERE deleted=0 AND student_id=?',(sid,)))['count']
    else:
        count=(await db.first('SELECT COUNT(*) AS count FROM star_record WHERE student_id=? AND action_code=? AND deleted=0',(sid,code)))['count']
    unlocked=[]
    for achievement in achievements:
        item=await unlock(db,owner,achievement,count)
        if item: unlocked.append(item)
    if code=='review_practice_set':
        dates=await db.all('SELECT DISTINCT date(created_at) AS date FROM star_record WHERE student_id=? AND action_code=\'review_practice_set\' AND deleted=0 ORDER BY date DESC LIMIT 31',(sid,))
        days={row['date'] for row in dates}
        from datetime import timedelta
        consecutive=0
        for index in range(30):
            if (now()-timedelta(days=index)).strftime('%Y-%m-%d') not in days: break
            consecutive+=1
        for achievement in await db.all('SELECT * FROM achievement WHERE code=\'continuous_learning\' AND deleted=0 ORDER BY level'):
            item=await unlock(db,owner,achievement,consecutive)
            if item: unlocked.append(item)
    return {'star_delta':action['star_value'],'new_balance':(await balance_row(db,owner))['balance'],'unlocked_achievements':unlocked}


@router.post('/motivation/trigger/review_word_accuracy')
async def word_accuracy(request: Request,total_count:int,correct_count:int,reason:str|None=None):
    """累计达到单词正确率要求的场次。"""
    db=Database(request.scope['env'].DB)
    owner=current_identity(request)
    config=await db.first('SELECT c.* FROM achievement_config c JOIN achievement a ON a.id=c.achievement_id WHERE a.code=\'word_accuracy\' AND a.deleted=0 LIMIT 1')
    accuracy=correct_count/total_count*100 if total_count>0 else 0
    if total_count<(config['min_words'] if config else 10) or accuracy<(config['min_accuracy'] if config else 90):
        return {'unlocked':False,'message':'未达成条件'}
    target=await db.first('SELECT a.*,COALESCE(p.current_count,0) AS current_count FROM achievement a LEFT JOIN achievement_progress p ON p.achievement_id=a.id AND p.student_id=? AND p.deleted=0 WHERE a.code=\'word_accuracy\' AND a.deleted=0 AND COALESCE(p.is_unlocked,0)=0 ORDER BY a.level LIMIT 1',
                          (owner['student_id'],))
    if not target: return {'unlocked':False,'message':'所有等级已解锁'}
    count=target['current_count']+1
    result=await unlock(db,owner,target,count)
    return {'unlocked':bool(result),'unlocked_achievements':[result] if result else [],'progress':{'level':target['level'],'current_count':count,'trigger_count':target['trigger_count']},'accuracy':accuracy,'total_count':total_count,'correct_count':correct_count}


@router.get('/motivation/overview')
async def overview(request:Request):
    """读取真实余额、成就和当日积分。"""
    db=Database(request.scope['env'].DB)
    owner=current_identity(request)
    sid=owner['student_id']
    counts=await db.first('SELECT (SELECT COUNT(*) FROM achievement WHERE deleted=0) AS achievement_total,'
                          '(SELECT COUNT(*) FROM achievement_progress p JOIN achievement a ON a.id=p.achievement_id WHERE p.student_id=? AND p.deleted=0 AND p.is_unlocked=1 AND a.deleted=0) AS achievement_unlocked,'
                          '(SELECT COUNT(*) FROM reward WHERE deleted=0 AND is_active=1 AND student_id=?) AS rewards_available',(sid,sid))
    today=await db.first('SELECT COALESCE(SUM(star_delta),0) AS total FROM star_record WHERE student_id=? AND deleted=0 AND created_at>=?',(sid,now().replace(hour=0,minute=0,second=0,microsecond=0).isoformat(' ')))
    return {'balance':(await balance_row(db,owner))['balance'],**counts,'today_stars':today['total']}


@router.get('/rewards/redemptions')
async def redemptions(request:Request):
    """读取兑换历史及奖励详情。"""
    db=Database(request.scope['env'].DB)
    sid=current_identity(request)['student_id']
    rows=await db.all('SELECT * FROM redemption WHERE deleted=0 AND student_id=? ORDER BY redeemed_at DESC LIMIT 50',(sid,))
    for row in rows: row['reward']=await db.first('SELECT * FROM reward WHERE id=? AND student_id=? AND deleted=0',(row['reward_id'],sid))
    return rows


@router.post('/rewards/{reward_id}/redeem')
async def redeem(reward_id:int,request:Request):
    """原子检查余额与库存，扣积分并保存兑换和流水；只能兑换自己学生的奖品。"""
    db=Database(request.scope['env'].DB)
    owner=current_identity(request)
    sid=owner['student_id']
    reward=await db.first('SELECT * FROM reward WHERE id=? AND student_id=? AND deleted=0 AND is_active=1',(reward_id,sid))
    if not reward: raise HTTPException(404,'奖励不存在或已下架')
    await balance_row(db,owner)
    stamp=now().isoformat(' ')
    try:
        await db.batch([('UPDATE write_guard SET revision=CASE WHEN (SELECT balance FROM star_balance WHERE student_id=? AND deleted=0)>=? AND EXISTS(SELECT 1 FROM reward WHERE id=? AND student_id=? AND is_active=1 AND deleted=0 AND (remaining_stock=-1 OR remaining_stock>0)) THEN revision+1 ELSE NULL END WHERE id=1',(sid,reward['cost_stars'],reward_id,sid)),
                        ('UPDATE star_balance SET balance=balance-?,updated_at=? WHERE student_id=? AND deleted=0',(reward['cost_stars'],stamp,sid)),
                        ('UPDATE reward SET remaining_stock=CASE WHEN remaining_stock>0 THEN remaining_stock-1 ELSE remaining_stock END WHERE id=? AND student_id=?',(reward_id,sid)),
                        ('INSERT INTO star_record(user_id,student_id,action_code,star_delta,balance_after,reason,deleted,created_at) '
                         'SELECT ?,student_id,\'redeem\',?,balance,?,0,? FROM star_balance WHERE student_id=? AND deleted=0',(owner['user_id'],-reward['cost_stars'],'兑换：'+reward['name'],stamp,sid)),
                        ('INSERT INTO redemption(user_id,student_id,reward_id,star_cost,redeemed_at) VALUES(?,?,?,?,?)',(owner['user_id'],sid,reward_id,reward['cost_stars'],stamp))])
    except Exception:
        raise HTTPException(400,'积分或库存不足，请刷新后重试')
    return {'success':True,'new_balance':(await balance_row(db,owner))['balance'],'reward_name':reward['name']}
