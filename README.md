# GoEmotions em Português (pt-BR)

Tradução para português do Brasil do [GoEmotions](https://github.com/google-research/google-research/tree/master/goemotions), um dataset de classificação de emoções com comentários do Reddit anotados com 28 rótulos de emoção (27 emoções e "neutral").

> **Status:** em andamento. Este repositório contém a tradução parcial. Veja [Status da tradução](#status-da-tradução).

## Sumário

- [Sobre](#sobre)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Formato dos dados](#formato-dos-dados)
- [Rótulos de emoção](#rótulos-de-emoção)
- [Estatísticas](#estatísticas)
- [Status da tradução](#status-da-tradução)
- [Como reproduzir](#como-reproduzir)
- [Limitações e cuidados](#limitações-e-cuidados)
- [Licença](#licença)
- [Citação](#citação)
- [Agradecimentos](#agradecimentos)

## Sobre

O GoEmotions original tem textos apenas em inglês. Este projeto traduz cada comentário para pt-BR, mantendo o tom, o registro informal, as gírias e a intensidade emocional do original. A tradução é feita automaticamente com o modelo Gemini (Google) por meio da API, a partir de um prompt que pede tradução natural e adaptada, não literal.

Os rótulos de emoção, os identificadores e a divisão treino/validação/teste são os do dataset original. Nenhum rótulo foi revisado ou alterado.

## Estrutura do repositório

```
.
├── raw/                  # Dados originais do GoEmotions (inglês)
│   ├── train.tsv         # Treino
│   ├── dev.tsv           # Validação
│   ├── test.tsv          # Teste
│   └── emotions.txt      # Lista dos 28 rótulos, na ordem dos índices
├── batches/              # Lotes intermediários (texto original + rótulos), gerados por prepare_batches.py
├── translated/           # Lotes traduzidos, um arquivo por lote (*_translated.json)
│   ├── failed_batches.txt                        # Lotes que falharam na tradução e o motivo
│   └── goemotions_pt_br_consolidated.jsonl       # Arquivo único gerado por consolidate.py
├── prepare_batches.py    # Divide os TSVs originais em lotes
├── translate.py          # Traduz os lotes com a API do Gemini
├── consolidate.py        # Junta os lotes traduzidos em um .jsonl
├── LICENSE               # Apache License 2.0
└── README.md
```

## Formato dos dados

O arquivo final é um JSON Lines (`.jsonl`), com um comentário por linha:

```json
{
  "id": "edgurhb",
  "split": "dev",
  "line_idx": 0,
  "original_text": "Is this in New Orleans?? I really feel like this is New Orleans.",
  "emotion_ids": "27",
  "emotions": ["neutral"],
  "translated_text": "Isso é em Nova Orleans?? Tenho muita pinta de ser em Nova Orleans."
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | Identificador do comentário no Reddit (igual ao do GoEmotions original). |
| `split` | string | Divisão original: `train`, `dev` ou `test`. |
| `line_idx` | int | Posição da linha no TSV original da divisão (0-based). |
| `original_text` | string | Texto original em inglês. |
| `emotion_ids` | string | Índices dos rótulos, separados por vírgula (ex.: `"4,27"`). Veja [Rótulos de emoção](#rótulos-de-emoção). |
| `emotions` | lista de string | Nomes dos rótulos correspondentes a `emotion_ids`. |
| `translated_text` | string | Tradução para pt-BR. |

Um mesmo comentário pode ter mais de um rótulo, como no original.

## Rótulos de emoção

| Índice | Rótulo | Índice | Rótulo |
|---|---|---|---|
| 0 | admiration | 14 | fear |
| 1 | amusement | 15 | gratitude |
| 2 | anger | 16 | grief |
| 3 | annoyance | 17 | joy |
| 4 | approval | 18 | love |
| 5 | caring | 19 | nervousness |
| 6 | confusion | 20 | optimism |
| 7 | curiosity | 21 | pride |
| 8 | desire | 22 | realization |
| 9 | disappointment | 23 | relief |
| 10 | disapproval | 24 | remorse |
| 11 | disgust | 25 | sadness |
| 12 | embarrassment | 26 | surprise |
| 13 | excitement | 27 | neutral |

## Estatísticas

Número de comentários por divisão no original (sem cabeçalho nos TSVs):

| Divisão | Comentários |
|---|---|
| train | 43.410 |
| dev | 5.426 |
| test | 5.427 |
| **Total** | **54.263** |

## Status da tradução

Contagem de 9 de novembro de 2026:

- Lotes de treino: 388 de 869 traduzidos.
- Lotes de validação: 10 de 10 traduzidos.
- Os lotes que falharam (por exemplo, por limite de tokens ou falha de rede) estão listados em `translated/failed_batches.txt`. Eles precisam ser reprocessados com `translate.py`.

Enquanto a tradução não estiver completa, o arquivo `goemotions_pt_br_consolidated.jsonl` **não contém o dataset inteiro**. Ele deve ser regenerado com `consolidate.py` ao final.

## Como reproduzir

Requisitos: Python 3.8+ (somente biblioteca padrão) e uma chave da API do Gemini, disponível gratuitamente em [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

```bash
# 1. Defina a chave (ou coloque GEMINI_API_KEY=... em um arquivo .env, que não é versionado)
export GEMINI_API_KEY=sua_chave

# 2. Gere os lotes: <split> <tamanho do lote> <máximo de lotes, 0 = todos>
python prepare_batches.py train 50 0
python prepare_batches.py dev 50 0
python prepare_batches.py test 50 0

# 3. Traduza (pula lotes já traduzidos, então pode ser reexecutado para retomar)
python translate.py
# Para testar com poucos lotes:
python translate.py --pattern "dev_*" --limit 2

# 4. Consolide em um único arquivo .jsonl
python consolidate.py
```

O modelo padrão é `gemini-3.1-flash-lite`, configurável por `--model` ou pela variável `GEMINI_MODEL`.

## Limitações e cuidados

- **Tradução automática, sem revisão humana.** Erros de tradução e de nuance emocional são esperados. Quem usar o dataset deve avaliar a qualidade na tarefa específica.
- **Rótulos herdados do original.** As anotações foram feitas em inglês, por anotadores de uma cultura específica. Elas podem não corresponder à percepção de falantes de português.
- **Conteúdo sensível.** Os textos vêm do Reddit e podem conter linguagem ofensiva, xingamentos e conteúdo adulto. Os dados foram mantidos como no original, sem censura.
- **Dados pessoais.** O GoEmotions original já substituiu nomes e menções por tokens como `[NAME]` e `[RELIGION]`. Esses tokens são mantidos na tradução.
- **Viés do modelo.** A tradução reflete os vieses do modelo usado.

## Licença

Este projeto é distribuído sob a [Apache License 2.0](LICENSE), a mesma licença do GoEmotions original.

A licença do GoEmotions original está em <https://huggingface.co/datasets/google-research-datasets/go_emotions> e <https://github.com/google-research/google-research/blob/master/LICENSE>. Ao redistribuir, mantenha a atribuição ao projeto original (veja [Citação](#citação)).

Os textos originais são comentários públicos do Reddit. Antes de usar este dataset comercialmente, confira os termos de uso do Reddit.

## Citação

Se você usar este dataset, cite o trabalho original do GoEmotions:

```bibtex
@inproceedings{demszky2020goemotions,
  author    = {Demszky, Dorottya and Movshovitz-Attias, Dana and Ko, Jeongwoo and Cowen, Alan and Nemade, Gaurav and Ravi, Sujith},
  title     = {{GoEmotions}: A Dataset of Fine-Grained Emotions},
  booktitle = {Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics},
  year      = {2020},
  url       = {https://arxiv.org/abs/2005.00547}
}
```

## Agradecimentos

Aos autores do GoEmotions (Google Research), pelo dataset original.
