/* eslint-disable @typescript-eslint/no-explicit-any -- a stand-in for a WebSocket, as open as the tests need */
/** A WebSocket that the test drives: it never connects by itself, and keeps every message the page sent. */
export class FakeSocket {
  static all: FakeSocket[] = []
  readyState = 0
  binaryType = ''
  sent: any[] = []
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string | Blob }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor(public url: string) {
    FakeSocket.all.push(this)
  }
  send(data: string) {
    this.sent.push(JSON.parse(data))
  }
  close() {
    this.readyState = 3
    this.onclose?.()
  }
  /** the server accepted the connection */
  open() {
    this.readyState = 1
    this.onopen?.()
  }
  /** the server says something */
  say(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) })
  }
  /** the server sends a picture */
  picture() {
    this.onmessage?.({ data: new Blob(['jpeg']) })
  }
}
