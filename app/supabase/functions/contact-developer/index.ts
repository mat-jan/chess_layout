// supabase/functions/contact-developer/index.ts
//
// Wiadomość do developera przez webhook Discorda — dostępna tylko dla zalogowanych
// nauczycieli i superadminów. Adres webhooka jest SEKRETEM po stronie Supabase
// (nigdy we froncie ani w repozytorium):
//
//   supabase secrets set DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
//   supabase functions deploy contact-developer
//
// Wywołanie: supabase.functions.invoke("contact-developer", { body: { message, subject? } })

import { createClient } from "jsr:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const MAX_MESSAGE = 1500;
const MAX_SUBJECT = 100;
const RATE_LIMIT = 5;            // wiadomości
const RATE_WINDOW_MS = 10 * 60_000; // na 10 minut, na użytkownika (best-effort, per instancja)
const sent = new Map<string, number[]>();

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Metoda niedozwolona" }, 405);

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) return json({ error: "Brak nagłówka Authorization" }, 401);

    const webhook = Deno.env.get("DISCORD_WEBHOOK_URL");
    if (!webhook) return json({ error: "Kontakt nie jest skonfigurowany" }, 503);

    const callerClient = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: authHeader } } },
    );

    const { data: { user }, error: userErr } = await callerClient.auth.getUser();
    if (userErr || !user) return json({ error: "Nieprawidłowa sesja" }, 401);

    const { data: profile, error: profileErr } = await callerClient
      .from("profiles").select("role").eq("id", user.id).single();
    if (profileErr || !["teacher", "superadmin"].includes(profile?.role)) {
      return json({ error: "Tylko nauczyciel lub superadmin może wysłać wiadomość" }, 403);
    }

    const now = Date.now();
    const recent = (sent.get(user.id) ?? []).filter((t) => now - t < RATE_WINDOW_MS);
    if (recent.length >= RATE_LIMIT) {
      return json({ error: "Zbyt wiele wiadomości. Spróbuj ponownie za kilka minut." }, 429);
    }

    const body = await req.json().catch(() => ({}));
    const message = typeof body.message === "string" ? body.message.trim() : "";
    const subject = typeof body.subject === "string" ? body.subject.trim() : "";
    if (!message) return json({ error: "Wiadomość nie może być pusta" }, 400);
    if (message.length > MAX_MESSAGE) return json({ error: `Maks. ${MAX_MESSAGE} znaków` }, 400);
    if (subject.length > MAX_SUBJECT) return json({ error: `Temat maks. ${MAX_SUBJECT} znaków` }, 400);

    const res = await fetch(webhook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: "Turniej Szachowy",
        // brak pingów @everyone/@role z treści wiadomości
        allowed_mentions: { parse: [] },
        embeds: [{
          title: subject || "Wiadomość z aplikacji",
          description: message,
          color: 0xd4af37,
          fields: [
            { name: "Od", value: user.email ?? user.id, inline: true },
            { name: "Rola", value: profile.role, inline: true },
          ],
          timestamp: new Date().toISOString(),
        }],
      }),
    });
    if (!res.ok) return json({ error: "Nie udało się wysłać wiadomości" }, 502);

    sent.set(user.id, [...recent, now]);
    return json({ ok: true }, 200);
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : "Nieznany błąd" }, 500);
  }
});

function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
