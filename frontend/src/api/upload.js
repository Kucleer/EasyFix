import axios from '@/api/http'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 图片上传：两个地址都由 Pages 网关直接写入 R2
export const uploadApi = {
  // 单张：表单字段 file，返回 { path, original_filename, size }
  uploadFile(file) {
    const form = new FormData()
    form.append('file', file)
    return api.post('/upload/file', form)
  },
  // 多张（一次最多 10 张）：表单字段 files，返回 { images: [{ success, image_path, ... }], ... }
  uploadImages(files) {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    return api.post('/upload/batch-simple', form)
  },
}

export default uploadApi
