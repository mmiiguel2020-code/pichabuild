// groq-spy — proxy local para VER que manda DSH, sin gastar cupo.
//
//   SPY_STUB=1  -> NO llama a Groq. Contesta un completion minimo y solo
//                  registra la peticion. Sirve para medir herramientas,
//                  chars, max_tokens y mensajes sin gastar el minuto.
//   sin SPY_STUB -> reenvia a Groq de verdad.
//
// Arranque:  node groq-spy.mjs | tee -a ~/pichadirector/spy.log
import http from 'node:http'
import { Readable } from 'node:stream'

const UPSTREAM = 'https://api.groq.com'
const PORT = Number(process.env.SPY_PORT || 8899)
const STUB = process.env.SPY_STUB === '1'
const HOP = ['host','connection','keep-alive','transfer-encoding','upgrade','content-length','accept-encoding']

const server = http.createServer(async (req, res) => {
  const chunks = []
  for await (const c of req) chunks.push(c)
  const body = Buffer.concat(chunks)
  let info = {}
  try {
    const j = JSON.parse(body.toString('utf8'))
    info = {
      model: j.model,
      tools: Array.isArray(j.tools) ? j.tools.length : 0,
      toolsChars: j.tools ? JSON.stringify(j.tools).length : 0,
      toolNames: Array.isArray(j.tools) ? j.tools.map(t => t?.function?.name ?? t?.name ?? '?') : [],
      msgs: Array.isArray(j.messages) ? j.messages.length : 0,
      msgsChars: j.messages ? JSON.stringify(j.messages).length : 0,
      max_tokens: j.max_completion_tokens ?? j.max_tokens ?? null,
      stream: !!j.stream,
    }
  } catch {}

  if (STUB) {
    console.log(JSON.stringify({ t: new Date().toISOString(), path: req.url, stub: true, bytes: body.length, ...info }))
    const reply = {
      id: 'chatcmpl-spy', object: 'chat.completion', created: Math.floor(Date.now()/1000),
      model: info.model || 'stub',
      choices: [{ index: 0, message: { role: 'assistant', content: 'ok' }, finish_reason: 'stop' }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    }
    if (info.stream) {
      res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' })
      res.write(`data: ${JSON.stringify({ ...reply, choices: [{ index: 0, delta: { role: 'assistant', content: 'ok' } }] })}\n\n`)
      res.write('data: [DONE]\n\n'); res.end()
    } else {
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify(reply))
    }
    return
  }

  const headers = {}
  for (const [k, v] of Object.entries(req.headers)) if (!HOP.includes(k)) headers[k] = v
  const hasBody = req.method !== 'GET' && req.method !== 'HEAD'
  try {
    const up = await fetch(UPSTREAM + req.url, { method: req.method, headers, body: hasBody ? body : undefined })
    const rl = {}
    for (const [k, v] of up.headers) if (k.startsWith('x-ratelimit') || k === 'retry-after') rl[k] = v
    console.log(JSON.stringify({ t: new Date().toISOString(), path: req.url, status: up.status, bytes: body.length, ...info, ...rl }))
    const out = {}
    up.headers.forEach((v, k) => { if (!['content-encoding','content-length','transfer-encoding','connection'].includes(k)) out[k] = v })
    res.writeHead(up.status, out)
    if (up.body) Readable.fromWeb(up.body).pipe(res); else res.end()
  } catch (e) {
    console.log(JSON.stringify({ t: new Date().toISOString(), error: String(e) }))
    res.writeHead(502); res.end('spy error')
  }
})
server.listen(PORT, '127.0.0.1', () => console.log(`groq-spy en http://127.0.0.1:${PORT} -> ${UPSTREAM}  (stub=${STUB})`))
