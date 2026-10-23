// supabase/functions/create-user/index.ts
//
// Wdrożenie:
//   supabase functions deploy create-user
//
// Sekrety (ustawiane automatycznie przez Supabase, nic nie trzeba robić):
//   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY
//
// Wywołanie z frontendu:
//   await supabase.functions.invoke('create-user', {
//     body: { email, password, role }   // role: 'teacher' | 'superadmin'
//   })
// Supabase automatycznie dołącza nagłówek Authorization z sesji wywołującego.

import { createClient } from "jsr:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return json({ error: "Brak nagłówka Authorization" }, 401);
    }

    // Klient "jako wywołujący" — do sprawdzenia KTO woła i jaką ma rolę.
    // Używa klucza anon + tokenu wywołującego, więc respektuje RLS.
    const callerClient = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: authHeader } } }
    );

    const { data: { user: caller }, error: callerErr } = await callerClient.auth.getUser();
    if (callerErr || !caller) {
      return json({ error: "Nieprawidłowa sesja" }, 401);
    }

    const { data: callerProfile, error: profileErr } = await callerClient
      .from("profiles")
      .select("role")
      .eq("id", caller.id)
      .single();

    if (profileErr || callerProfile?.role !== "superadmin") {
      return json({ error: "Tylko superadmin może tworzyć konta" }, 403);
    }

    const { email, password, role } = await req.json();

    if (!email || !password || !role) {
      return json({ error: "Wymagane: email, password, role" }, 400);
    }
    if (!["teacher", "superadmin"].includes(role)) {
      return json({ error: "role musi być 'teacher' lub 'superadmin'" }, 400);
    }
    if (password.length < 8) {
      return json({ error: "Hasło musi mieć min. 8 znaków" }, 400);
    }

    // Klient admina — service_role, omija RLS, tworzy użytkownika naprawdę.
    const adminClient = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const { data: created, error: createErr } = await adminClient.auth.admin.createUser({
      email,
      password,
      email_confirm: true,
    });

    if (createErr || !created.user) {
      return json({ error: createErr?.message ?? "Nie udało się utworzyć konta" }, 400);
    }

    const { error: insertErr } = await adminClient
      .from("profiles")
      .insert({ id: created.user.id, email, role });

    if (insertErr) {
      // sprzątanie — jeśli profil się nie zapisał, nie zostawiaj osieroconego konta auth
      await adminClient.auth.admin.deleteUser(created.user.id);
      return json({ error: insertErr.message }, 400);
    }

    return json({ id: created.user.id, email, role }, 201);
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
