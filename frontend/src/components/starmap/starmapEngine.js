// 知识星空的 canvas 绘制与动画（红黄绿方案）。
// 布局用 d3-force，缩放和拖动用 d3-zoom；画面全部在 canvas 上逐帧绘制。
// 星星只用"圆点 + 光晕"表示，掌握得越好光晕越大越亮，不画星芒。

import { forceSimulation, forceLink, forceManyBody, forceX, forceY, forceCollide } from 'd3-force'
import { zoom as d3zoom, zoomIdentity } from 'd3-zoom'
import { select } from 'd3-selection'
import { colorOf, lighten, between } from './starmapColors.js'

const MASTER_GREEN = '88,214,141'
const BACKGROUND = '#030306'

// 把接口数据整理成绘制用的节点和连线（复制一份，避免改到外面的数据）
function prepare(data) {
  const nodes = (data.nodes || []).map(n => ({ ...n }))
  const ids = new Set(nodes.map(n => n.id))
  const links = (data.links || []).filter(l => ids.has(l.source) && ids.has(l.target)).map(l => ({ ...l }))
  const childCount = {}
  nodes.forEach(n => { if (n.level === 2) childCount[n.parent_id] = (childCount[n.parent_id] || 0) + 1 })
  nodes.forEach(n => { n.childCount = childCount[n.id] || 0 })
  if (data.vocab) {
    // 英语的词汇星团：一颗不连线的大星，大小随阶段长大
    nodes.push({ id: 'vocab', name: '词汇', level: 1, value: data.vocab.ratio, stage: data.vocab.stage, vocab: data.vocab, childCount: 0 })
  }
  return { nodes, links }
}

// 节点半径：二级考点统一大小（靠颜色区分），模块随考点数变大，词汇星随阶段变大
function radiusOf(node, scale) {
  if (node.id === 'vocab') return (7 + node.stage * 2.2) * scale
  if (node.level === 1) return (3.4 + node.childCount * 0.25) * scale
  return (node.value === null ? 1.8 : 2.65) * scale
}

export function createStarEngine(canvas, data, options = {}) {
  const mini = !!options.mini
  const scale = mini ? 0.62 : 1
  const ctx = canvas.getContext('2d')
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const { nodes, links } = prepare(data)
  let width = 0
  let height = 0
  let transform = zoomIdentity
  let hover = null
  let near = null
  let time = 0
  let raf = 0
  let running = true
  const bursts = []
  const rings = []

  function resize() {
    width = canvas.clientWidth
    height = canvas.clientHeight
    canvas.width = width * dpr
    canvas.height = height * dpr
  }
  resize()

  // 力导向布局：先算一段让图形稳定，之后保持极轻微的漂移
  const simulation = forceSimulation(nodes)
    .force('link', forceLink(links).id(d => d.id).distance(l => (l.kind === 'belongs' ? 40 : 75) * scale).strength(l => (l.kind === 'belongs' ? 0.8 : 0.12)))
    .force('charge', forceManyBody().strength(d => (d.level === 2 ? -70 : -380) * scale))
    .force('x', forceX(() => width / 2).strength(0.09))
    .force('y', forceY(() => height / 2).strength(0.13))
    .force('collide', forceCollide(d => radiusOf(d, scale) + 9 * scale))
    .alphaDecay(0.02)
    .stop()
  for (let i = 0; i < 260; i++) simulation.tick()
  simulation.alphaTarget(0.006).restart()

  // 背景：细密微尘、淡淡的装饰网络、若隐若现的淡字（缩略图不画淡字）
  const dust = Array.from({ length: mini ? 260 : 900 }, () => ({
    x: Math.random(), y: Math.random(), r: Math.random() * 0.9 + 0.15, a: Math.random() * 0.45 + 0.08,
    p: Math.random() * 6.28, s: Math.random() * 0.8 + 0.3, z: Math.random(),
  }))
  const words = mini ? [] : (options.background || []).map(text => ({
    text, x: 0.05 + Math.random() * 0.9, y: 0.08 + Math.random() * 0.86, a: Math.random() * 0.08 + 0.05,
    size: 12 + Math.random() * 8, drift: (Math.random() - 0.5) * 0.00003,
  }))
  const decor = Array.from({ length: mini ? 70 : 220 }, () => ({ x: Math.random(), y: Math.random(), r: Math.random() + 0.4, p: Math.random() * 6.28, z: Math.random() * 0.6 + 0.2 }))
  const decorLinks = []
  decor.forEach((a, i) => {
    decor.map((b, j) => [j, Math.hypot((a.x - b.x) * 1.6, a.y - b.y)])
      .filter(([j]) => j !== i).sort((u, v) => u[1] - v[1]).slice(0, 2)
      .forEach(([j, d]) => { if (d < 0.16 && i < j) decorLinks.push([a, decor[j]]) })
  })
  // 流动的光点：只在两端掌握度都不低于 0.45 的连线上
  const flows = []
  links.forEach(l => {
    const v = Math.min(l.source.value ?? 0, l.target.value ?? 0)
    if (v >= 0.45) for (let i = 0; i < (l.kind === 'prereq' ? 2 : 1); i++) {
      flows.push({ link: l, t: Math.random(), speed: (Math.random() * 0.0025 + 0.0015) * (l.kind === 'prereq' ? 1.4 : 1) })
    }
  })

  function glow(x, y, r, a, color) {
    if (a <= 0.01 || r <= 0) return
    const g = ctx.createRadialGradient(x, y, 0, x, y, r)
    g.addColorStop(0, `rgba(${color},${a})`)
    g.addColorStop(0.35, `rgba(${color},${a * 0.35})`)
    g.addColorStop(1, `rgba(${color},0)`)
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(x, y, r, 0, 6.283)
    ctx.fill()
  }

  function draw() {
    time += 1
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.globalCompositeOperation = 'source-over'
    ctx.fillStyle = BACKGROUND
    ctx.fillRect(0, 0, width, height)
    // 远处的淡字，不随缩放
    for (const w of words) {
      w.x += w.drift
      ctx.font = `${w.size}px "Cambria Math","Times New Roman",serif`
      ctx.fillStyle = `rgba(200,206,222,${w.a})`
      ctx.fillText(w.text, w.x * width, w.y * height)
    }
    ctx.globalCompositeOperation = 'lighter'
    for (const d of dust) {
      const px = (d.x * width + transform.x * d.z * 0.15 + time * 0.02 * d.s) % width
      const py = (d.y * height + transform.y * d.z * 0.15) % height
      ctx.fillStyle = `rgba(215,222,240,${d.a * (0.5 + 0.5 * Math.sin(time * 0.02 * d.s + d.p))})`
      ctx.fillRect((px + width) % width, (py + height) % height, d.r * 1.4, d.r * 1.4)
    }
    const dx = d => ((d.x * width + transform.x * d.z * 0.25) % width + width) % width
    const dy = d => ((d.y * height + transform.y * d.z * 0.25) % height + height) % height
    ctx.lineWidth = 0.5
    for (const [a, b] of decorLinks) {
      const ax = dx(a), ay = dy(a), bx = dx(b), by = dy(b)
      if (Math.abs(ax - bx) > width / 3 || Math.abs(ay - by) > height / 3) continue
      ctx.strokeStyle = `rgba(160,168,190,${0.09 + 0.05 * Math.sin(time * 0.01 + a.p)})`
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke()
    }
    for (const d of decor) glow(dx(d), dy(d), d.r * 4, 0.3 + 0.2 * Math.sin(time * 0.025 + d.p), '170,178,200')

    ctx.save()
    ctx.translate(transform.x, transform.y)
    ctx.scale(transform.k, transform.k)
    // 连线：颜色取两端中间色；与悬停星相连的线更亮更粗
    for (const l of links) {
      const v = Math.min(l.source.value ?? 0.05, l.target.value ?? 0.05)
      const on = hover && (l.source === hover || l.target === hover)
      const color = between(colorOf(l.source.value), colorOf(l.target.value))
      const alpha = on ? 0.95 : (l.kind === 'prereq' ? 0.16 + v * 0.6 : 0.1 + v * 0.42)
      ctx.strokeStyle = `rgba(${on ? lighten(color, 0.25) : color},${alpha})`
      ctx.lineWidth = (on ? 1.8 : l.kind === 'prereq' ? 0.9 : 0.6) / Math.sqrt(transform.k)
      ctx.beginPath(); ctx.moveTo(l.source.x, l.source.y); ctx.lineTo(l.target.x, l.target.y); ctx.stroke()
    }
    for (const f of flows) {
      const on = hover && (f.link.source === hover || f.link.target === hover)
      f.t = (f.t + f.speed * (on ? 2.5 : 1)) % 1
      const s = f.link.source, t = f.link.target
      glow(s.x + (t.x - s.x) * f.t, s.y + (t.y - s.y) * f.t, (on ? 6 : 4) * scale, on ? 0.95 : 0.55, colorOf(t.value))
    }
    // 星星：没学的只有一个灰点；学过的按掌握度画光晕，掌握得越好光晕越大越亮
    for (const n of nodes) {
      const r = radiusOf(n, scale)
      const color = colorOf(n.value)
      const v = Math.max(n.value ?? 0.05, 0.05)
      const breathe = 0.85 + 0.15 * Math.sin(time * 0.03 + n.x * 0.05)
      if (n.value !== null) {
        glow(n.x, n.y, r * (2.5 + v * 9) * breathe, 0.18 + v * 0.62, color)
        if (v >= 0.6) glow(n.x, n.y, r * (1.5 + v * 3), 0.25 + (v - 0.6) * 1.2, lighten(color, 0.3))
      }
      ctx.fillStyle = `rgba(${lighten(color, 0.35)},${n.value === null ? 0.35 : 0.9})`
      ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 6.283); ctx.fill()
      if (near && near.has(n.id)) glow(n.x, n.y, r * (n === hover ? 10 : 6), n === hover ? 0.55 : 0.3, color)
      if (n === hover) {
        for (let k = 0; k < 2; k++) {
          const phase = ((time * 0.012) + k * 0.5) % 1
          ctx.strokeStyle = `rgba(${lighten(color, 0.3)},${(1 - phase) * 0.8})`
          ctx.lineWidth = 1.2 / transform.k
          ctx.beginPath(); ctx.arc(n.x, n.y, r + phase * 26, 0, 6.283); ctx.stroke()
        }
      }
    }
    // 点亮时刻：扩散的光环和迸发的绿色粒子
    for (let i = rings.length - 1; i >= 0; i--) {
      const g = rings[i]
      g.r += 1.6; g.a *= 0.965
      if (g.a < 0.02) { rings.splice(i, 1); continue }
      ctx.strokeStyle = `rgba(${MASTER_GREEN},${g.a})`; ctx.lineWidth = 1.2
      ctx.beginPath(); ctx.arc(g.x, g.y, g.r, 0, 6.283); ctx.stroke()
    }
    for (let i = bursts.length - 1; i >= 0; i--) {
      const b = bursts[i]
      b.x += b.vx; b.y += b.vy; b.vx *= 0.96; b.vy *= 0.96; b.life -= 1
      if (b.life <= 0) { bursts.splice(i, 1); continue }
      glow(b.x, b.y, b.r * 3, b.life / b.max, MASTER_GREEN)
    }
    ctx.restore()
    ctx.globalCompositeOperation = 'source-over'
  }

  function frame() {
    if (!running) return
    draw()
    raf = requestAnimationFrame(frame)
  }

  function start() {
    if (running && raf) return
    running = true
    simulation.restart()
    raf = requestAnimationFrame(frame)
  }

  function stop() {
    running = false
    cancelAnimationFrame(raf)
    raf = 0
    simulation.stop()
  }

  // 页面切到后台时停止绘制，回来时恢复
  function onVisibility() { if (document.hidden) stop(); else start() }
  document.addEventListener('visibilitychange', onVisibility)
  window.addEventListener('resize', resize)

  // 屏幕坐标下最近的星（在半径加 10 像素的范围内）
  function findAt(px, py) {
    const [x, y] = transform.invert([px, py])
    let best = null
    let bestDistance = Infinity
    for (const n of nodes) {
      const d = Math.hypot(n.x - x, n.y - y)
      if (d < bestDistance && d < radiusOf(n, scale) + 10 / transform.k) { bestDistance = d; best = n }
    }
    return best
  }

  function setHover(node) {
    hover = node
    near = null
    if (!node) return
    near = new Set([node.id])
    links.forEach(l => {
      if (l.source === node) near.add(l.target.id)
      if (l.target === node) near.add(l.source.id)
    })
  }

  // 缩略图不响应缩放和鼠标；全屏时由引擎处理悬停和点击，再通知外面
  let zoomBehavior = null
  const handlers = []
  if (!mini) {
    zoomBehavior = d3zoom().scaleExtent([0.4, 4]).on('zoom', event => { transform = event.transform })
    select(canvas).call(zoomBehavior)
    const move = event => {
      const node = findAt(event.offsetX, event.offsetY)
      if (node !== hover) setHover(node)
      canvas.style.cursor = node ? 'pointer' : 'grab'
      options.onHover?.(node, node ? screenOf(node.id) : null)
    }
    const leave = () => { setHover(null); options.onHover?.(null, null) }
    const click = event => options.onSelect?.(findAt(event.offsetX, event.offsetY))
    canvas.addEventListener('mousemove', move)
    canvas.addEventListener('mouseleave', leave)
    canvas.addEventListener('click', click)
    handlers.push(['mousemove', move], ['mouseleave', leave], ['click', click])
  }

  function screenOf(id) {
    const node = nodes.find(n => n.id === id)
    return node ? transform.apply([node.x, node.y]) : null
  }

  // 点亮：考点变为掌握（绿色），扩散光环并迸发粒子
  function light(ids) {
    for (const id of ids) {
      const node = nodes.find(n => n.id === id)
      if (!node) continue
      node.value = 1
      rings.push({ x: node.x, y: node.y, r: radiusOf(node, scale), a: 0.9 })
      for (let i = 0; i < 110; i++) {
        const angle = Math.random() * 6.28, speed = Math.random() * 2.2 + 0.4, life = 50 + Math.random() * 60
        bursts.push({ x: node.x, y: node.y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, r: Math.random() * 1.2 + 0.5, life, max: life })
      }
    }
  }

  function destroy() {
    stop()
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('resize', resize)
    handlers.forEach(([name, fn]) => canvas.removeEventListener(name, fn))
    if (zoomBehavior) select(canvas).on('.zoom', null)
  }

  raf = requestAnimationFrame(frame)
  return { setHover, findAt, screenOf, light, resize, destroy }
}
