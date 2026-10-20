# Artigo 2 — notas metodológicas congeladas

## Desfechos

- Cerebrovascular mortality: I60–I69, causa básica.
- Dementia-related mortality: F00–F03 + G30, causa básica.
- Alzheimer-specific mortality: F00 + G30, causa básica.
- Parkinson disease mortality: G20, causa básica.
- Sensibilidade: dementia-related mortality excluindo F01.

## Denominadores

IBGE — Projeções da População do Brasil e Unidades da Federação, Revisão 2024, 2000–2070, população por sexo e grupos quinquenais.

## Taxa específica

r(a,t) = deaths(a,t) / population(a,t) × 100,000.

## Padronização direta

ASMR(t) = Σ w(a) × r(a,t),

com pesos normalizados da WHO World Standard 2000–2025.

A planilha IBGE encerra a distribuição em 90+. Portanto:

w(90+) = w(90–94) + w(95–99) + w(100+) = 0.15 + 0.04 + 0.005.

Como os pesos publicados são arredondados e somam 100,035, todos os pesos são divididos pela soma publicada antes do cálculo.

## Erro-padrão da ASMR

Assumindo contagens de óbitos Poisson e denominadores fixos:

Var(ASMR) = 100000² × Σ [w(a)² × d(a) / n(a)²].

SE = sqrt(Var).

IC95% normal: ASMR ± 1.96 × SE, com limite inferior truncado em zero.

## Neuroepidemiological Transition Index

NTI(t) = ASMR_dementia(t) / ASMR_cerebrovascular(t).

Para IC95%, utiliza-se aproximação delta na escala log:

SE[log(NTI)] ≈ sqrt[(SE_dem/r_dem)² + (SE_cvd/r_cvd)²].

Isso assume independência aproximada entre as duas contagens de causa básica; o NTI será tratado como índice descritivo/inferencial secundário, não como desfecho causal.

## Joinpoint

Input oficial preparado em ASCII tab-delimited com Rate e StandardError.

Configuração pré-especificada:

- annual interval;
- log transformation;
- 0–4 joinpoints;
- Monte Carlo permutation model selection/significance;
- APC por segmento;
- AAPC 2000–2024;
- IC95%.

## Decomposição

Para um ano t:

D = N × Σ S(a)R(a),

onde:

- N = tamanho populacional total;
- S(a) = proporção populacional do grupo etário a;
- R(a) = taxa de mortalidade específica por idade.

Três componentes:

1. population growth: N0 → N1;
2. population ageing: S0 → S1;
3. mortality-rate change: R0 → R1.

A contribuição Shapley de cada componente é a média do efeito marginal do componente nas seis ordens possíveis de mudança dos três fatores. Assim, a decomposição não depende de uma ordem arbitrária e a soma das contribuições reconstrói exatamente D1 − D0 para os óbitos com idade conhecida.

## Idade desconhecida

- Taxas brutas: incluem óbitos de idade desconhecida no numerador total.
- ASMR/decomposição: exigem idade conhecida.
- A proporção de idade desconhecida é exportada por causa, ano e geografia para QC.

## Estratificações

Primária: Brasil, ambos os sexos.

Pré-especificadas:

- Male/Female;
- cinco regiões;
- UFs para descrição/mapas;
- pré-pandemia 2000–2019;
- série completa 2000–2024.