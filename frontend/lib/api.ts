import type {
  CategoriaClima, ClimaPrevisto, Lugar, Metricas, Opcoes, Periodo, Previsao, Rota, TrechosGeoJSON,
} from "./tipos";

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    let mensagem = `Erro ${resp.status}`;
    try {
      const corpo = await resp.json();
      if (typeof corpo.detail === "string") mensagem = corpo.detail;
    } catch {
      // resposta sem JSON (ex.: backend fora do ar)
    }
    if (resp.status >= 500 && mensagem.startsWith("Erro")) {
      mensagem = "Não foi possível falar com o servidor. Ele está rodando?";
    }
    throw new Error(mensagem);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  trechos: () => pedir<TrechosGeoJSON>("/api/trechos"),
  opcoes: () => pedir<Opcoes>("/api/opcoes"),
  modelo: () => pedir<Metricas>("/api/modelo"),

  prever: (
    corpo: {
      trecho_ids: string[];
      data: string;
      periodo: Periodo;
      clima: CategoriaClima;
      clima_personalizado?: { chuva_mm: number; nebulosidade: number; temperatura?: number } | null;
    },
    signal?: AbortSignal,
  ) => pedir<Previsao>("/api/prever", { method: "POST", body: JSON.stringify(corpo), signal }),

  rota: (origem: Lugar, destino: Lugar, signal?: AbortSignal) =>
    pedir<Rota>("/api/rota", {
      method: "POST",
      body: JSON.stringify({
        origem: { lat: origem.lat, lon: origem.lon },
        destino: { lat: destino.lat, lon: destino.lon },
      }),
      signal,
    }),

  buscar: (q: string, signal?: AbortSignal) =>
    pedir<Lugar[]>(`/api/busca?q=${encodeURIComponent(q)}`, { signal }),

  climaPrevisto: (trechoId: string, data: string, periodo: Periodo) =>
    pedir<ClimaPrevisto>(
      `/api/clima-previsto?trecho_id=${encodeURIComponent(trechoId)}&data=${data}&periodo=${periodo}`,
    ),
};
