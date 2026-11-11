-- 0013：知识星空的种子数据。由 cloudflare/scripts/build_starmap_seed.py 生成，不要手改。
-- 全部语句可以重复执行（已存在的跳过）。

-- 1. 英语语法新体系（一级在前）
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NOU','名词','名词',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,100,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NOU' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRO','代词用法','代词用法',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,200,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRO' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NUM','数词与冠词','数词与冠词',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,300,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NUM' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRE','介词与连词','介词与连词',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,400,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRE' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-ADJ','形容词副词与比较','形容词副词与比较',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,500,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-ADJ' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-TEN','动词时态','动词时态',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,600,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-TEN' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-VRB','情态动词与非谓语','情态动词与非谓语',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,700,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-VRB' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-WRD','构词法','构词法',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,800,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-WRD' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-SEN','句子类型','句子类型',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,900,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-SEN' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-CLA','句型与复合句','句型与复合句',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,1000,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-CLA' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PHO','语音知识','语音知识',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,1100,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PHO' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-COM','交际用语','交际用语',1,NULL,(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,NULL,1200,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-COM' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NOU-01','名词单复数','名词单复数',2,(SELECT id FROM knowledge_point WHERE code='EG-NOU' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,101,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NOU-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NOU-02','可数名词与不可数名词','可数名词与不可数名词',2,(SELECT id FROM knowledge_point WHERE code='EG-NOU' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,4,102,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NOU-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NOU-03','名词所有格','名词所有格',2,(SELECT id FROM knowledge_point WHERE code='EG-NOU' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,103,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NOU-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRO-01','人称代词主格与宾格','人称代词主格与宾格',2,(SELECT id FROM knowledge_point WHERE code='EG-PRO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,201,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRO-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRO-02','物主代词','物主代词',2,(SELECT id FROM knowledge_point WHERE code='EG-PRO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,4,202,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRO-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRO-03','指示代词','指示代词',2,(SELECT id FROM knowledge_point WHERE code='EG-PRO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,203,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRO-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRO-04','疑问代词','疑问代词',2,(SELECT id FROM knowledge_point WHERE code='EG-PRO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,4,204,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRO-04' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRO-05','不定代词','不定代词',2,(SELECT id FROM knowledge_point WHERE code='EG-PRO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,205,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRO-05' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRO-06','反身代词','反身代词',2,(SELECT id FROM knowledge_point WHERE code='EG-PRO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,206,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRO-06' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NUM-01','基数词','基数词',2,(SELECT id FROM knowledge_point WHERE code='EG-NUM' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,301,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NUM-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NUM-02','序数词','序数词',2,(SELECT id FROM knowledge_point WHERE code='EG-NUM' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,302,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NUM-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NUM-03','不定冠词 a / an','不定冠词 a / an',2,(SELECT id FROM knowledge_point WHERE code='EG-NUM' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,303,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NUM-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-NUM-04','定冠词 the 与零冠词','定冠词 the 与零冠词',2,(SELECT id FROM knowledge_point WHERE code='EG-NUM' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,304,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-NUM-04' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRE-01','方位介词','方位介词',2,(SELECT id FROM knowledge_point WHERE code='EG-PRE' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,401,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRE-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRE-02','时间介词','时间介词',2,(SELECT id FROM knowledge_point WHERE code='EG-PRE' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,4,402,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRE-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRE-03','介词短语与固定搭配','介词短语与固定搭配',2,(SELECT id FROM knowledge_point WHERE code='EG-PRE' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,403,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRE-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PRE-04','并列连词','并列连词',2,(SELECT id FROM knowledge_point WHERE code='EG-PRE' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,404,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PRE-04' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-ADJ-01','形容词作定语与表语','形容词作定语与表语',2,(SELECT id FROM knowledge_point WHERE code='EG-ADJ' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,501,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-ADJ-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-ADJ-02','形容词与副词的区分','形容词与副词的区分',2,(SELECT id FROM knowledge_point WHERE code='EG-ADJ' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,502,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-ADJ-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-ADJ-03','比较级','比较级',2,(SELECT id FROM knowledge_point WHERE code='EG-ADJ' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,503,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-ADJ-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-ADJ-04','最高级','最高级',2,(SELECT id FROM knowledge_point WHERE code='EG-ADJ' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,504,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-ADJ-04' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-ADJ-05','频度副词','频度副词',2,(SELECT id FROM knowledge_point WHERE code='EG-ADJ' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,505,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-ADJ-05' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-TEN-01','一般现在时','一般现在时',2,(SELECT id FROM knowledge_point WHERE code='EG-TEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,601,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-TEN-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-TEN-02','现在进行时','现在进行时',2,(SELECT id FROM knowledge_point WHERE code='EG-TEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,4,602,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-TEN-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-TEN-03','一般过去时','一般过去时',2,(SELECT id FROM knowledge_point WHERE code='EG-TEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,603,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-TEN-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-TEN-04','一般将来时','一般将来时',2,(SELECT id FROM knowledge_point WHERE code='EG-TEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,604,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-TEN-04' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-TEN-05','过去进行时','过去进行时',2,(SELECT id FROM knowledge_point WHERE code='EG-TEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,605,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-TEN-05' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-TEN-06','现在完成时','现在完成时',2,(SELECT id FROM knowledge_point WHERE code='EG-TEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,8,606,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-TEN-06' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-TEN-07','被动语态','被动语态',2,(SELECT id FROM knowledge_point WHERE code='EG-TEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,8,607,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-TEN-07' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-VRB-01','情态动词 can / may','情态动词 can / may',2,(SELECT id FROM knowledge_point WHERE code='EG-VRB' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,701,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-VRB-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-VRB-02','情态动词 must / have to / should','情态动词 must / have to / should',2,(SELECT id FROM knowledge_point WHERE code='EG-VRB' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,702,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-VRB-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-VRB-03','动词不定式','动词不定式',2,(SELECT id FROM knowledge_point WHERE code='EG-VRB' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,703,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-VRB-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-VRB-04','动名词','动名词',2,(SELECT id FROM knowledge_point WHERE code='EG-VRB' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,704,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-VRB-04' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-VRB-05','分词作定语','分词作定语',2,(SELECT id FROM knowledge_point WHERE code='EG-VRB' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,7,705,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-VRB-05' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-WRD-01','合成词','合成词',2,(SELECT id FROM knowledge_point WHERE code='EG-WRD' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,801,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-WRD-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-WRD-02','派生词与词形转换','派生词与词形转换',2,(SELECT id FROM knowledge_point WHERE code='EG-WRD' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,802,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-WRD-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-SEN-01','肯定句与否定句','肯定句与否定句',2,(SELECT id FROM knowledge_point WHERE code='EG-SEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,901,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-SEN-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-SEN-02','一般疑问句','一般疑问句',2,(SELECT id FROM knowledge_point WHERE code='EG-SEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,902,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-SEN-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-SEN-03','特殊疑问句','特殊疑问句',2,(SELECT id FROM knowledge_point WHERE code='EG-SEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,4,903,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-SEN-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-SEN-04','选择疑问句与反意疑问句','选择疑问句与反意疑问句',2,(SELECT id FROM knowledge_point WHERE code='EG-SEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,7,904,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-SEN-04' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-SEN-05','祈使句','祈使句',2,(SELECT id FROM knowledge_point WHERE code='EG-SEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,905,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-SEN-05' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-SEN-06','感叹句','感叹句',2,(SELECT id FROM knowledge_point WHERE code='EG-SEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,906,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-SEN-06' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-SEN-07','句型转换与语序','句型转换与语序',2,(SELECT id FROM knowledge_point WHERE code='EG-SEN' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,907,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-SEN-07' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-CLA-01','there be 句型','there be 句型',2,(SELECT id FROM knowledge_point WHERE code='EG-CLA' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,4,1001,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-CLA-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-CLA-02','主谓一致','主谓一致',2,(SELECT id FROM knowledge_point WHERE code='EG-CLA' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,1002,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-CLA-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-CLA-03','简单句的基本句型','简单句的基本句型',2,(SELECT id FROM knowledge_point WHERE code='EG-CLA' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,7,1003,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-CLA-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-CLA-04','状语从句','状语从句',2,(SELECT id FROM knowledge_point WHERE code='EG-CLA' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,1004,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-CLA-04' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-CLA-05','宾语从句','宾语从句',2,(SELECT id FROM knowledge_point WHERE code='EG-CLA' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,8,1005,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-CLA-05' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-CLA-06','定语从句','定语从句',2,(SELECT id FROM knowledge_point WHERE code='EG-CLA' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,9,1006,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-CLA-06' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PHO-01','字母与字母组合发音','字母与字母组合发音',2,(SELECT id FROM knowledge_point WHERE code='EG-PHO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,1101,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PHO-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PHO-02','单词重音','单词重音',2,(SELECT id FROM knowledge_point WHERE code='EG-PHO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,1102,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PHO-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-PHO-03','句子重音与语调','句子重音与语调',2,(SELECT id FROM knowledge_point WHERE code='EG-PHO' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,6,1103,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-PHO-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-COM-01','问候与介绍','问候与介绍',2,(SELECT id FROM knowledge_point WHERE code='EG-COM' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,3,1201,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-COM-01' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-COM-02','感谢、赞扬与提供帮助','感谢、赞扬与提供帮助',2,(SELECT id FROM knowledge_point WHERE code='EG-COM' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,4,1202,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-COM-02' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-COM-03','建议与应答','建议与应答',2,(SELECT id FROM knowledge_point WHERE code='EG-COM' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,1203,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-COM-03' AND deleted=0);
INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,deleted,created_at,updated_at)
  SELECT 'EG-COM-04','请求与许可','请求与许可',2,(SELECT id FROM knowledge_point WHERE code='EG-COM' AND deleted=0),(SELECT id FROM subject WHERE name='英语' AND deleted=0),NULL,5,1204,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM knowledge_point WHERE code='EG-COM-04' AND deleted=0);

-- 2. 数学教材的节与考点对应（沪教版（五四制，2024）六年级上册）
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',1,'有理数','1.1','有理数',11,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='1.1' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.1' AND s.deleted=0 AND k.code='M6-RAT-01' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.1' AND s.deleted=0 AND k.code='M6-RAT-02' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.1' AND s.deleted=0 AND k.code='M6-RAT-03' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.1' AND s.deleted=0 AND k.code='M6-RAT-04' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.1' AND s.deleted=0 AND k.code='M6-RAT-05' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.1' AND s.deleted=0 AND k.code='M6-RAT-06' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',1,'有理数','1.2','有理数的加法与减法',12,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='1.2' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.2' AND s.deleted=0 AND k.code='M6-RAT-07' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.2' AND s.deleted=0 AND k.code='M6-APP-01' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',1,'有理数','1.3','有理数的乘法与除法',13,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='1.3' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.3' AND s.deleted=0 AND k.code='M6-RAT-08' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',1,'有理数','1.4','有理数的乘方',14,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='1.4' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.4' AND s.deleted=0 AND k.code='M6-RAT-09' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',1,'有理数','1.5','有理数的混合运算',15,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='1.5' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.5' AND s.deleted=0 AND k.code='M6-RAT-10' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='1.5' AND s.deleted=0 AND k.code='M6-RAT-11' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',2,'简单的代数式','2.1','用字母表示数',21,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='2.1' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='2.1' AND s.deleted=0 AND k.code='M6-ALG-03' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',2,'简单的代数式','2.2','代数式',22,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='2.2' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='2.2' AND s.deleted=0 AND k.code='M6-ALG-04' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='2.2' AND s.deleted=0 AND k.code='M6-ALG-05' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='2.2' AND s.deleted=0 AND k.code='M6-ALG-02' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',2,'简单的代数式','2.3','一次式',23,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='2.3' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='2.3' AND s.deleted=0 AND k.code='M6-ALG-01' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',3,'一元一次方程','3.1','方程与列方程',31,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='3.1' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='3.1' AND s.deleted=0 AND k.code='M6-EQU-02' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',3,'一元一次方程','3.2','一元一次方程及其解法',32,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='3.2' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='3.2' AND s.deleted=0 AND k.code='M6-EQU-01' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',3,'一元一次方程','3.3','一元一次方程的应用',33,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='3.3' AND deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',4,'线段与角','4.1','线段',41,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='4.1' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='4.1' AND s.deleted=0 AND k.code='M6-LIN-01' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,section_name,sort_order,deleted,created_at)
  SELECT 1,(SELECT id FROM subject WHERE name='数学' AND deleted=0),'沪教版（五四制，2024）六年级上册',4,'线段与角','4.2','角',42,0,CURRENT_TIMESTAMP
  WHERE NOT EXISTS (SELECT 1 FROM textbook_section WHERE textbook='沪教版（五四制，2024）六年级上册' AND section_no='4.2' AND deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='4.2' AND s.deleted=0 AND k.code='M6-LIN-02' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);
INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)
  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k
  WHERE s.textbook='沪教版（五四制，2024）六年级上册' AND s.section_no='4.2' AND s.deleted=0 AND k.code='M6-LIN-03' AND k.deleted=0
    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND x.knowledge_point_id=k.id AND x.deleted=0);

-- 3. 先学后学连线
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-DIV-03' AND a.deleted=0 AND b.code='M6-DIV-01' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-DIV-01' AND a.deleted=0 AND b.code='M6-DIV-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-DIV-02' AND a.deleted=0 AND b.code='M6-FRA-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-FRA-01' AND a.deleted=0 AND b.code='M6-FRA-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-FRA-02' AND a.deleted=0 AND b.code='M6-FRA-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-FRA-03' AND a.deleted=0 AND b.code='M6-FRA-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-FRA-02' AND a.deleted=0 AND b.code='M6-FRA-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-FRA-05' AND a.deleted=0 AND b.code='M6-FRA-06' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-01' AND a.deleted=0 AND b.code='M6-RAT-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-02' AND a.deleted=0 AND b.code='M6-RAT-03' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-02' AND a.deleted=0 AND b.code='M6-RAT-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-04' AND a.deleted=0 AND b.code='M6-RAT-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-05' AND a.deleted=0 AND b.code='M6-RAT-06' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-05' AND a.deleted=0 AND b.code='M6-RAT-07' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-07' AND a.deleted=0 AND b.code='M6-RAT-08' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-FRA-05' AND a.deleted=0 AND b.code='M6-RAT-08' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-08' AND a.deleted=0 AND b.code='M6-RAT-09' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-09' AND a.deleted=0 AND b.code='M6-RAT-10' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-07' AND a.deleted=0 AND b.code='M6-RAT-10' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-10' AND a.deleted=0 AND b.code='M6-RAT-11' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-07' AND a.deleted=0 AND b.code='M6-APP-01' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-ALG-03' AND a.deleted=0 AND b.code='M6-ALG-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-ALG-03' AND a.deleted=0 AND b.code='M6-ALG-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-ALG-03' AND a.deleted=0 AND b.code='M6-ALG-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-10' AND a.deleted=0 AND b.code='M6-ALG-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-ALG-02' AND a.deleted=0 AND b.code='M6-ALG-01' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-ALG-03' AND a.deleted=0 AND b.code='M6-PAT-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-FRA-05' AND a.deleted=0 AND b.code='M6-PAT-01' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-ALG-01' AND a.deleted=0 AND b.code='M6-EQU-01' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-ALG-03' AND a.deleted=0 AND b.code='M6-EQU-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-EQU-01' AND a.deleted=0 AND b.code='M6-EQU-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-EQU-02' AND a.deleted=0 AND b.code='M6-APP-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-EQU-02' AND a.deleted=0 AND b.code='M6-APP-03' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-FRA-06' AND a.deleted=0 AND b.code='M6-APP-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-RAT-03' AND a.deleted=0 AND b.code='M6-LIN-01' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-LIN-01' AND a.deleted=0 AND b.code='M6-LIN-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='M6-LIN-02' AND a.deleted=0 AND b.code='M6-LIN-03' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-NOU-01' AND a.deleted=0 AND b.code='EG-NOU-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-NOU-02' AND a.deleted=0 AND b.code='EG-CLA-01' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-PRO-01' AND a.deleted=0 AND b.code='EG-PRO-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-PRO-02' AND a.deleted=0 AND b.code='EG-PRO-06' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-NUM-03' AND a.deleted=0 AND b.code='EG-NUM-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-NUM-01' AND a.deleted=0 AND b.code='EG-NUM-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-PRE-01' AND a.deleted=0 AND b.code='EG-PRE-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-PRE-02' AND a.deleted=0 AND b.code='EG-PRE-03' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-ADJ-01' AND a.deleted=0 AND b.code='EG-ADJ-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-ADJ-01' AND a.deleted=0 AND b.code='EG-ADJ-03' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-ADJ-03' AND a.deleted=0 AND b.code='EG-ADJ-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-01' AND a.deleted=0 AND b.code='EG-ADJ-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-01' AND a.deleted=0 AND b.code='EG-TEN-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-01' AND a.deleted=0 AND b.code='EG-TEN-03' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-01' AND a.deleted=0 AND b.code='EG-TEN-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-02' AND a.deleted=0 AND b.code='EG-TEN-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-03' AND a.deleted=0 AND b.code='EG-TEN-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-03' AND a.deleted=0 AND b.code='EG-TEN-06' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-03' AND a.deleted=0 AND b.code='EG-TEN-07' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-TEN-01' AND a.deleted=0 AND b.code='EG-CLA-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-VRB-01' AND a.deleted=0 AND b.code='EG-VRB-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-VRB-03' AND a.deleted=0 AND b.code='EG-VRB-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-VRB-04' AND a.deleted=0 AND b.code='EG-VRB-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-WRD-01' AND a.deleted=0 AND b.code='EG-WRD-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-SEN-01' AND a.deleted=0 AND b.code='EG-SEN-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-SEN-02' AND a.deleted=0 AND b.code='EG-SEN-03' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-SEN-03' AND a.deleted=0 AND b.code='EG-SEN-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-SEN-02' AND a.deleted=0 AND b.code='EG-SEN-07' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-SEN-03' AND a.deleted=0 AND b.code='EG-CLA-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-PRE-04' AND a.deleted=0 AND b.code='EG-CLA-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-CLA-03' AND a.deleted=0 AND b.code='EG-CLA-05' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-CLA-05' AND a.deleted=0 AND b.code='EG-CLA-06' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-PHO-01' AND a.deleted=0 AND b.code='EG-PHO-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-PHO-02' AND a.deleted=0 AND b.code='EG-PHO-03' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-COM-01' AND a.deleted=0 AND b.code='EG-COM-02' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);
INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)
  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b
  WHERE a.code='EG-COM-02' AND a.deleted=0 AND b.code='EG-COM-04' AND b.deleted=0
    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id AND x.deleted=0);

-- 4. 考点目录有变化，统计缓存随之失效
UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE name='taxonomy_version' AND deleted=0;
UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE name='data_revision' AND deleted=0;
