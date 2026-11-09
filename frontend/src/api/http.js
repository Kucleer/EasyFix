import axios from 'axios'

// 缓存仅存在于当前页面内存，写入成功即清空，不持久化私密数据。
const cached = new Map()
const pending = new Map()
let generation = 0

function lifetime(config) {
  if ((config.method || 'get').toLowerCase() !== 'get' || config.cache === false) return 0
  const url = String(config.url || '')
  if (/\/config\/llm|\/auth\/|\/audio|\/uploads\//.test(url)) return 0
  if (/\/(subjects|tags|knowledge-points|error-types)$|\/config\/app$/.test(url)) return 300000
  if (/\/stats\//.test(url)) return 30000
  return 10000
}

function install(instance) {
  const adapter = axios.getAdapter(instance.defaults.adapter)
  instance.defaults.adapter = async config => {
    const ttl = lifetime(config)
    const key = instance.getUri(config) + '|' + (config.responseType || 'json')
    if (ttl) {
      const hit = cached.get(key)
      if (hit && hit.expires > Date.now()) return { ...hit.response, data: structuredClone(hit.response.data), config }
      if (pending.has(key)) {
        const response = await pending.get(key)
        return { ...response, data: structuredClone(response.data), config }
      }
    }
    const version = generation
    const operation = adapter(config).then(response => {
      if (ttl && response.status >= 200 && response.status < 300 && version === generation) {
        if (cached.size >= 100) cached.delete(cached.keys().next().value)
        cached.set(key, { expires: Date.now() + ttl, response: { ...response, data: structuredClone(response.data) } })
      } else if (!['get', 'head', 'options'].includes((config.method || 'get').toLowerCase()) && response.status >= 200 && response.status < 300) {
        generation += 1
        cached.clear()
      }
      return response
    }).catch(error => {
      let body = error.response?.data
      if (typeof body === 'string') { try { body = JSON.parse(body) } catch {} }
      if (error.response?.status === 409 && body?.cloud_url === 'https://easyfix-bl2.pages.dev' && ['localhost', '127.0.0.1'].includes(window.location.hostname)) {
        window.location.replace(body.cloud_url + window.location.pathname + window.location.search)
      } else if (error.response?.status === 401 && !String(config.url).includes('/auth/')) {
        cached.clear()
        if (window.location.hostname.endsWith('.pages.dev')) window.location.replace('/login')
      }
      throw error
    }).finally(() => { if (pending.get(key) === operation) pending.delete(key) })
    if (ttl) pending.set(key, operation)
    return operation
  }
  return instance
}

const client = install(axios.create())
client.create = config => install(axios.create(config))
client.isAxiosError = axios.isAxiosError
client.isCancel = axios.isCancel
client.CancelToken = axios.CancelToken
export default client
