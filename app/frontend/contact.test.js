// @vitest-environment node
import { describe, it, expect, afterEach } from "vitest";
import http from "node:http";
import { sendContactMessage, buildContactPayload } from "./contact.js";

let server;
afterEach(() => new Promise(r => (server ? server.close(r) : r())));

function start(status) {
  const got = [];
  return new Promise(resolve => {
    server = http.createServer((req, res) => {
      let body = "";
      req.on("data", c => (body += c));
      req.on("end", () => { got.push({ method: req.method, type: req.headers["content-type"], body: JSON.parse(body) }); res.statusCode = status; res.end(); });
    }).listen(0, () => resolve({ url: `http://127.0.0.1:${server.address().port}/hook`, got }));
  });
}

describe("sendContactMessage (bez Supabase)", () => {
  it("POSTuje embed JSON na webhook", async () => {
    const { url, got } = await start(204);
    await sendContactMessage(url, { subject: "Błąd", message: " Nie działa ", senderEmail: "n@szkola.pl", role: "teacher" });
    expect(got).toHaveLength(1);
    expect(got[0].method).toBe("POST");
    expect(got[0].type).toBe("application/json");
    const e = got[0].body.embeds[0];
    expect(e.title).toBe("Błąd");
    expect(e.description).toBe("Nie działa");
    expect(e.fields.map(f => f.value)).toEqual(["n@szkola.pl", "teacher"]);
    expect(got[0].body.allowed_mentions).toEqual({ parse: [] });
  });
  it("zgłasza błąd, gdy Discord odrzuci", async () => {
    const { url } = await start(400);
    await expect(sendContactMessage(url, { message: "x" })).rejects.toThrow(/400/);
  });
  it("wymaga webhooka i treści", async () => {
    await expect(sendContactMessage("", { message: "x" })).rejects.toThrow(/skonfigurowany/);
    await expect(sendContactMessage("http://x", { message: "  " })).rejects.toThrow(/wiadomość/i);
  });
  it("przycina zbyt długie pola", () => {
    const p = buildContactPayload({ subject: "a".repeat(500), message: "b".repeat(5000) });
    expect(p.embeds[0].title.length).toBe(100);
    expect(p.embeds[0].description.length).toBe(1500);
  });
});
