# Roteiro da apresentação — Risco de acidentes nas rodovias de SC

Duração sugerida: **15 min** (11 min de slides + 3 min de demonstração + 1 min de fechamento), e depois perguntas.
Os gráficos de apoio saem do `projeto_final.ipynb` (seção indicada em cada slide).

**Equipe:** Gustavo Ross · Kevin C. El Azar · Guilherme Assis · Bredley Bauer · Gabriel Coelho · Gustavo Haiduk

| # | Slide | Mensagem principal | Apoio |
|---|---|---|---|
| 1 | Título | Qual a chance de acidente neste trecho, dia e período? | captura `docs/img/previsao.png` |
| 2 | Problema e público | Acidentes se concentram em poucos trechos e horários; motoristas, PRF/DER e Defesa Civil precisam saber *onde e quando* | tabela de público (notebook §1) |
| 3 | Dados | 6 fontes públicas; 74,6 mil acidentes da PRF (2017–2025) e 148 mil do RENAEST casados a rodovias estaduais (2019–mai/2026) | gráfico de acidentes por ano (§2) |
| 4 | O desafio do RENAEST | Em SC não há coordenadas nem km, só o endereço digitado → limpeza + casamento com o OpenStreetMap (~90%); regra da maioria para uma rua não virar rodovia | exemplo "ROD JOSE CARLOS DAUX" → SC-401 (§4) |
| 5 | Exploração | 10% dos trechos concentram 49% (BRs) e 65% (estaduais) dos acidentes; o alvo é raro (2–3%) → acurácia não serve | curva de concentração (§3) |
| 6 | Tratamentos | Histórico sem vazamento (só até o dia anterior), trechos sem acidente, clima de todos os dias, nível de notificação do RENAEST | tabela de tratamentos (§4) |
| 7 | Modelo | HistGradientBoosting por rede; trecho × dia × período; divisão **temporal** (testa no último ano); comparado com o histórico puro e a logística/PCA | §5 |
| 8 | Resultados | ROC-AUC 0,83 (BRs) e 0,90 (estaduais); os 10% de maior risco concentram 51% e 66% dos acidentes; probabilidades calibradas | tabela + curva de calibração (§6) |
| 9 | A conclusão honesta | O modelo supera por pouco o histórico do trecho: o risco é sobretudo *onde*. O modelo acrescenta o *quando*. Clima e tráfego quase não ajudam | ROC/PR com a linha de base; clima por subconjunto (§6) |
| 10 | Erros e limitações | Erra nos trechos movimentados que mudam de patamar (BR-280 Araquari, SC-412 Itajaí) e na madrugada; notificação e casamento no RENAEST | §7 e §9 |
| 11 | Demonstração | (ao vivo, ver abaixo) | — |
| 12 | Conclusões e futuro | Serve para comparar e priorizar, não para garantir segurança; próximos passos: gravidade, PRF 2026, km nas estaduais | §8 e §9 |

## Roteiro da demonstração (3 min)

Antes: `bash rodar.sh` aberto e http://localhost:3000 já carregado (o primeiro carregamento demora).

1. **Mapa de risco:** mostrar as duas redes (BR em linha contínua, estaduais tracejadas) e as cores por acidentes
   por km.
2. **Trecho perigoso:** clicar na BR-101 km 200–210 (São José), escolher **noite** e depois **chuva forte**;
   mostrar a chance, a comparação com a média do trecho e o "Por que esse valor?".
3. **Feriado:** trocar a data para "Próximo feriado" e mostrar o fator mudando.
4. **Planejar viagem** (`/viagem`): Florianópolis → Blumenau; mostrar os trechos de BR e estaduais da rota e a
   chance combinada.
5. **Rankings:** filtrar estaduais e ordenar por "Por 10 km/ano": SC-405 e SC-406, em Florianópolis, no topo.
6. **Plano B sem internet** (OSRM/Nominatim fora do ar), no terminal:
   ```bash
   cd backend
   .venv/bin/python -m scripts.prever --rodovia BR-101 --km 205 --data 2026-12-24 --periodo noite --clima chuva_forte
   ```

## Perguntas prováveis e respostas curtas

- **Por que o modelo quase empata com o histórico?** Porque o maior determinante do risco é o local: trechos
  movimentados e urbanos acumulam acidentes ano após ano. O modelo ganha em todas as métricas, de forma consistente
  nas duas redes, e acrescenta o efeito de período, dia e feriado. Mostrar isso é parte do resultado.
- **Por que não acurácia?** Com 2–3% de positivos, prever sempre "sem acidente" acerta ~98%. Por isso usamos
  ROC-AUC, PR-AUC (que se compara com a taxa base), Brier, calibração e captura nos k% de maior risco.
- **Por que divisão temporal e não aleatória?** No uso real o modelo prevê o futuro. Uma divisão aleatória
  deixaria dias vizinhos do teste no treino e inflaria as métricas.
- **Há vazamento?** O histórico do trecho só usa até o dia anterior (testado em `tests/test_features.py`); o clima
  vem de uma reanálise de todos os dias, não do boletim do acidente (que só existe quando há acidente).
- **O RENAEST é confiável?** É a melhor base de acidentes estaduais disponível, mas depende do envio de cada
  Detran (caiu em 2024) e não tem localização exata. Tratamos com o nível de notificação e o casamento de
  endereços, e deixamos as limitações explícitas na interface.
- **Por que o clima não ajuda?** A chuva forte reduz o tráfego e aumenta o risco por veículo, e os dois efeitos se
  compensam. Além disso, a reanálise tem resolução de ~25 km. Na média, a chuva forte aumenta um pouco o risco
  previsto, mas não melhora a ordenação.
- **Por que HistGradientBoosting?** Capta interações não lineares (local × período), aceita ausentes e categorias,
  permite restrição monotônica e treina rápido em ~3 milhões de linhas. Venceu a regressão logística, e o PCA não
  ajudou (estudo em `notebooks/estudos/`).
