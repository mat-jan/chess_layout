// Wspólna logika turnieju (używana przez wersję Supabase i VPS) — czyste funkcje, łatwe do testowania.

export function generateBuergerPairs(participants, round) {
  const sorted = [...participants].sort((a, b) =>
    a.imie.localeCompare(b.imie, "pl")
  );
  const n = sorted.length;
  if (n < 2) return [];

  let order;
  if (n % 2 === 0) {
    const fixed = sorted[0];
    const rest  = sorted.slice(1);
    const shift = (round - 1) % (n - 1);
    const rotated = [...rest.slice(shift), ...rest.slice(0, shift)];
    order = [fixed, ...rotated];
  } else {
    const shift = (round - 1) % n;
    order = [...sorted.slice(shift), ...sorted.slice(0, shift)];
    order.splice(0, 0, null);
  }

  const half   = order.length / 2;
  const top    = order.slice(0, half);
  const bottom = order.slice(half).reverse();

  return top.map((white, i) => {
    const black = bottom[i];
    if (white === null) return { round_number: round, white_id: black.id, black_id: null, result: "wolny los" };
    if (black === null) return { round_number: round, white_id: white.id, black_id: null, result: "wolny los" };
    return { round_number: round, white_id: white.id, black_id: black.id, result: "" };
  });
}

export function scoreFor(p, pairs) {
  let pts = 0;
  pairs.forEach(pair => {
    const isW = pair.white_id === p.id;
    const isB = pair.black_id === p.id;
    if (!isW && !isB) return;
    if (pair.result==="1-0")       pts += isW ? 1 : 0;
    if (pair.result==="0-1")       pts += isB ? 1 : 0;
    if (pair.result==="0.5-0.5")   pts += .5;
    if (pair.result==="wolny los" && !pair.black_id) pts += 1;
  });
  return pts;
}
