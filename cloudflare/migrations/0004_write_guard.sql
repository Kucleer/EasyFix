CREATE TABLE write_guard(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL,deleted INTEGER NOT NULL DEFAULT 0);
INSERT INTO write_guard(id,revision,deleted) VALUES(1,0,0);
CREATE UNIQUE INDEX cloudflare_star_balance_user ON star_balance(user_id);
