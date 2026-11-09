INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES('data_revision','0',0,CURRENT_TIMESTAMP) ON CONFLICT(name) DO NOTHING;
