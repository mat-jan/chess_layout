// Wysyłka wiadomości do developera na webhook Discorda (bez backendu).
export const CONTACT_MAX_MESSAGE = 1500;
export const CONTACT_MAX_SUBJECT = 100;

export function buildContactPayload({ subject = "", message, senderEmail, role }) {
  return {
    username: "Turniej Szachowy",
    allowed_mentions: { parse: [] }, // brak pingów @everyone/@role z treści
    embeds: [{
      title: (subject.trim() || "Wiadomość z aplikacji").slice(0, CONTACT_MAX_SUBJECT),
      description: message.trim().slice(0, CONTACT_MAX_MESSAGE),
      color: 0xd4af37,
      fields: [
        { name: "Od", value: senderEmail || "?", inline: true },
        { name: "Rola", value: role || "?", inline: true },
      ],
      timestamp: new Date().toISOString(),
    }],
  };
}

export async function sendContactMessage(webhook, data, fetchImpl = fetch) {
  if (!webhook) throw new Error("Kontakt nie jest skonfigurowany.");
  if (!data.message || !data.message.trim()) throw new Error("Wpisz wiadomość.");
  const res = await fetchImpl(webhook, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildContactPayload(data)),
  });
  if (!res.ok) throw new Error("Discord odrzucił wiadomość (" + res.status + ")");
}
