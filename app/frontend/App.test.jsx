import { describe, it, expect } from "vitest";
import { generateBuergerPairs, scoreFor } from "./App.jsx";

function p(id, imie, klasa = "1A") {
  return { id, imie, klasa };
}

describe("generateBuergerPairs", () => {
  it("returns no pairs for fewer than 2 participants", () => {
    expect(generateBuergerPairs([], 1)).toEqual([]);
    expect(generateBuergerPairs([p(1, "Jan")], 1)).toEqual([]);
  });

  it("pairs every participant exactly once for an even roster", () => {
    const participants = [p(1, "Ala"), p(2, "Bob"), p(3, "Cezary"), p(4, "Dawid")];
    const pairs = generateBuergerPairs(participants, 1);
    const seen = new Set();
    pairs.forEach(({ white_id, black_id }) => {
      seen.add(white_id);
      if (black_id != null) seen.add(black_id);
    });
    expect(pairs.length).toBe(2);
    expect(seen.size).toBe(4);
  });

  it("gives exactly one bye for an odd roster, each round", () => {
    const participants = [p(1, "Ala"), p(2, "Bob"), p(3, "Cezary")];
    for (let round = 1; round <= 3; round++) {
      const pairs = generateBuergerPairs(participants, round);
      const byes = pairs.filter(pr => pr.black_id == null);
      expect(byes.length).toBe(1);
      expect(byes[0].result).toBe("wolny los");
    }
  });

  it("rotates pairings across rounds without immediate repeats for odd roster", () => {
    const participants = [p(1, "Ala"), p(2, "Bob"), p(3, "Cezary"), p(4, "Dawid"), p(5, "Ewa")];
    const seenPerRound = [1, 2, 3, 4].map(r => {
      const pairs = generateBuergerPairs(participants, r);
      return new Set(
        pairs
          .filter(pr => pr.black_id != null)
          .map(pr => [pr.white_id, pr.black_id].sort().join("-"))
      );
    });
    // No exact pairing set should repeat across these rounds (Berger rotation).
    const flat = seenPerRound.flatMap(s => [...s]);
    const asSet = new Set(flat);
    expect(asSet.size).toBe(flat.length);
  });
});

describe("scoreFor", () => {
  const a = { id: 1 }, b = { id: 2 };
  it("scores wins, draws and byes regardless of bye side", () => {
    const pairs = [
      { white_id: 1, black_id: 2, result: "1-0" },
      { white_id: 1, black_id: 2, result: "0.5-0.5" },
      { white_id: 1, black_id: null, result: "wolny los" },
    ];
    expect(scoreFor(a, pairs)).toBe(2.5);
    expect(scoreFor(b, pairs)).toBe(0.5);
    expect(scoreFor(b, [{ white_id: 3, black_id: null, result: "wolny los" }])).toBe(0);
  });
});
