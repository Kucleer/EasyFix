// 网关上传接口的测试：用假的 R2、D1 和后端代替真实云端。
// 运行：node --test cloudflare/pages/worker.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './_worker.js';

const TOKEN = 'test-token';
const SITE = 'https://easyfix.test';

/** 造一套假的云端环境，并记录写进 R2、D1 和转给后端的内容。 */
function makeEnv({ maintenance = null, dbBroken = false } = {}) {
  const stored = new Map();   // R2 里保存的对象：key -> { size, contentType }
  const logs = [];            // 写进 operation_log 的参数
  const backendCalls = [];    // 转给 Python 后端的请求路径
  const env = {
    ACCESS_TOKEN: TOKEN,
    IMAGES: {
      async put(key, value, options) {
        stored.set(key, { size: value.byteLength, contentType: options.httpMetadata.contentType });
      },
    },
    DB: {
      prepare(sql) {
        return {
          async first() {
            if (dbBroken) throw new Error('D1 读取失败');
            return maintenance === null ? null : { value: maintenance };
          },
          bind(...values) {
            return { async run() { logs.push({ sql, values }); } };
          },
        };
      },
    },
    BACKEND: {
      async fetch(request) {
        backendCalls.push(new URL(request.url).pathname);
        return Response.json({ from: 'backend' });
      },
    },
  };
  return { env, stored, logs, backendCalls };
}

/** 造一个上传请求；files 是 [字段名, 文件名, 类型, 字节数] 的列表。 */
function uploadRequest(path, files, headers = { Authorization: 'Bearer ' + TOKEN }) {
  const form = new FormData();
  for (const [field, name, type, size] of files) {
    form.append(field, new File([new Uint8Array(size)], name, { type }));
  }
  return new Request(SITE + path, { method: 'POST', body: form, headers });
}

test('批量上传：图片直接写入 R2，不经过 Python 后端', async () => {
  const { env, stored, logs, backendCalls } = makeEnv();
  const response = await worker.fetch(uploadRequest('/api/upload/batch-simple', [
    ['files', 'page1.jpg', 'image/jpeg', 2048],
    ['files', 'a/b.png', 'image/png', 100],
  ]), env);
  assert.equal(response.status, 200);
  const data = await response.json();
  assert.equal(data.total_count, 2);
  assert.equal(data.success_count, 2);
  assert.equal(data.failed_count, 0);
  // 路径是「年/月/8位随机_文件名」，文件名里的斜杠换成下划线
  assert.match(data.images[0].path, /^\d{4}\/\d{2}\/[0-9a-f]{8}_page1\.jpg$/);
  assert.match(data.images[1].path, /^\d{4}\/\d{2}\/[0-9a-f]{8}_a_b\.png$/);
  assert.equal(data.images[0].image_path, data.images[0].path);
  assert.equal(data.images[0].original_filename, 'page1.jpg');
  assert.equal(data.images[0].size, 2048);
  assert.equal(data.images[0].success, true);
  assert.deepEqual(stored.get(data.images[0].path), { size: 2048, contentType: 'image/jpeg' });
  assert.deepEqual(stored.get(data.images[1].path), { size: 100, contentType: 'image/png' });
  assert.deepEqual(backendCalls, []);
  // 和后端一样记一条操作日志
  assert.equal(logs.length, 1);
  assert.equal(logs[0].values[0], 'upload');
});

test('批量上传：不合格的图片逐项说明原因，合格的照常保存', async () => {
  const { env, stored } = makeEnv();
  const response = await worker.fetch(uploadRequest('/api/upload/batch-simple', [
    ['files', 'note.txt', 'text/plain', 10],
    ['files', 'empty.jpg', 'image/jpeg', 0],
    ['files', 'ok.webp', 'image/webp', 10],
  ]), env);
  const data = await response.json();
  assert.equal(response.status, 200);
  assert.deepEqual(data.images[0], { original_filename: 'note.txt', success: false, error: '不支持的图片类型' });
  assert.deepEqual(data.images[1], { original_filename: 'empty.jpg', success: false, error: '图片为空或超过10MB' });
  assert.equal(data.images[2].success, true);
  assert.equal(data.success_count, 1);
  assert.equal(data.failed_count, 2);
  assert.equal(stored.size, 1);
});

test('批量上传：超过 10 张或没有图片返回 422', async () => {
  const { env, stored } = makeEnv();
  const eleven = Array.from({ length: 11 }, (_, i) => ['files', i + '.jpg', 'image/jpeg', 10]);
  const tooMany = await worker.fetch(uploadRequest('/api/upload/batch-simple', eleven), env);
  assert.equal(tooMany.status, 422);
  assert.equal((await tooMany.json()).detail, '每批最多10张图片');
  const none = await worker.fetch(uploadRequest('/api/upload/batch-simple', []), env);
  assert.equal(none.status, 422);
  assert.equal(stored.size, 0);
});

test('上传前的检查：没登录 401、维护中 503、跨站来源 403，都不写 R2', async () => {
  const files = [['files', 'page.jpg', 'image/jpeg', 10]];
  const cases = [
    [makeEnv(), {}, 401],
    [makeEnv(), { Authorization: 'Bearer wrong' }, 401],
    [makeEnv({ maintenance: 'on' }), { Authorization: 'Bearer ' + TOKEN }, 503],
    // 维护开关读不出来时按维护中处理，不默认放行写入
    [makeEnv({ dbBroken: true }), { Authorization: 'Bearer ' + TOKEN }, 503],
    [makeEnv(), { Authorization: 'Bearer ' + TOKEN, Origin: 'https://evil.test' }, 403],
  ];
  for (const [made, headers, status] of cases) {
    const response = await worker.fetch(uploadRequest('/api/upload/batch-simple', files, headers), made.env);
    assert.equal(response.status, status);
    assert.equal(made.stored.size, 0);
    assert.deepEqual(made.backendCalls, []);
  }
  // 维护开关关闭、同站来源：正常保存
  const made = makeEnv({ maintenance: '0' });
  const ok = await worker.fetch(uploadRequest('/api/upload/batch-simple', files,
    { Authorization: 'Bearer ' + TOKEN, Origin: SITE }), made.env);
  assert.equal(ok.status, 200);
  assert.equal(made.stored.size, 1);
});

test('单张上传 /api/upload/file：返回原接口字段，不合格返回 400', async () => {
  const { env, stored, backendCalls } = makeEnv();
  const good = await worker.fetch(uploadRequest('/api/upload/file', [['file', 'page.jpg', 'image/jpeg', 300]]), env);
  assert.equal(good.status, 200);
  const data = await good.json();
  assert.deepEqual(Object.keys(data).sort(), ['original_filename', 'path', 'size']);
  assert.match(data.path, /^\d{4}\/\d{2}\/[0-9a-f]{8}_page\.jpg$/);
  assert.equal(data.size, 300);
  assert.equal(stored.size, 1);
  const bad = await worker.fetch(uploadRequest('/api/upload/file', [['file', 'doc.pdf', 'application/pdf', 300]]), env);
  assert.equal(bad.status, 400);
  assert.equal((await bad.json()).detail, '不支持的图片类型');
  assert.equal(stored.size, 1);
  assert.deepEqual(backendCalls, []);
});

test('不是表单的上传请求返回 422', async () => {
  const { env } = makeEnv();
  const request = new Request(SITE + '/api/upload/batch-simple', {
    method: 'POST', body: '{}',
    headers: { Authorization: 'Bearer ' + TOKEN, 'Content-Type': 'application/json' },
  });
  assert.equal((await worker.fetch(request, env)).status, 422);
});

test('其他接口仍然转给 Python 后端', async () => {
  const { env, stored, backendCalls } = makeEnv();
  await worker.fetch(uploadRequest('/api/upload/to-error-book/3', [['files', 'p.jpg', 'image/jpeg', 10]]), env);
  await worker.fetch(new Request(SITE + '/api/subjects'), env);
  await worker.fetch(new Request(SITE + '/health'), env);
  assert.deepEqual(backendCalls, ['/api/upload/to-error-book/3', '/api/subjects', '/health']);
  assert.equal(stored.size, 0);
});
