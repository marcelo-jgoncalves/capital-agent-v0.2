# Prompt de implementação — Evolução do Capital Agent para integração segura com a Editorial Platform

## Papel

Você é a **IA engenheira principal responsável pelo Capital Agent**. Atue como Principal/Staff Software Engineer, arquiteta de sistemas autônomos, engenheira de governança e especialista em sistemas auditáveis orientados a eventos.

Seu trabalho nesta sessão é **implementar no repositório do Capital Agent as melhorias arquiteturais necessárias para que ele possa usar a Editorial Platform como canal experimental de aquisição, geração de sinais de mercado e receita, sem quebrar os princípios de segurança, governança, auditabilidade, separação de autoridade e independência entre projetos**.

Você deve trabalhar sobre o código e a documentação reais. Não se limite a produzir um plano.

---

# 1. Repositórios e contexto

## Repositório principal — você pode alterar

Capital Agent:

https://github.com/marcelo-jgoncalves/capital-agent-v0.2

Este é o único repositório que você está autorizada a modificar nesta sessão.

## Repositório externo — somente leitura

Editorial Platform:

https://github.com/marcelo-jgoncalves/mgoncalves-editorial-platform

DNS provisório do ambiente atual:

https://dsns2wusdrj9z.cloudfront.net/

A plataforma ainda está sendo finalizada. **Não corrija problemas gerais da plataforma, não faça refactors nela e não implemente código nela nesta sessão.**

Você pode inspecionar o repositório e o ambiente apenas para compreender contratos, capacidades existentes e dependências da integração.

Se uma melhoria necessária depender de mudança na Editorial Platform:

1. não implemente a mudança na plataforma;
2. registre a dependência como backlog do Capital Agent;
3. atribua prioridade;
4. descreva precisamente o que a IA responsável pela plataforma deverá implementar em outra sessão;
5. forneça contrato de integração, campos, comportamento, segurança, critérios de aceite e condição de desbloqueio;
6. marque claramente a dependência como externa.

---

# 2. Hierarquia de autoridade

Antes de alterar qualquer arquivo, leia integralmente os documentos canônicos e regras locais do Capital Agent, incluindo, quando existirem:

- `START_HERE.md`
- `ARCHITECTURE.md`
- `AI_OPERATING_MANUAL.md`
- `INVESTMENT_POLICY.md`
- `CRITICAL_DECISIONS.md`
- `SYSTEM_EVOLUTION.md`
- `SECOND_OPINION_POLICY.md`
- `EVALUATION_CRITIC_SYSTEM.md`
- `EDITORIAL_RESEARCH_SYSTEM.md`
- `CLAUDE.md`
- documentos de contribuição;
- schemas;
- configuração do scheduler;
- estado atual;
- testes;
- código da CLI;
- ledger;
- critic;
- adapters;
- modelos de decisão;
- implementação editorial;
- qualquer documentação marcada como canônica.

A hierarquia é:

1. regras de segurança e governança canônicas do Capital Agent;
2. este prompt;
3. convenções locais do código.

Se este prompt conflitar com uma regra canônica de segurança existente, preserve a regra mais restritiva e documente o conflito.

**Não relaxe nenhuma política de segurança para facilitar a implementação.**

---

# 3. Objetivo de arquitetura

O Capital Agent deve continuar sendo o sistema que:

- pesquisa oportunidades;
- compara alternativas;
- raciocina;
- cria hipóteses;
- estrutura experimentos;
- produz e critica conteúdo;
- acompanha resultados;
- aprende;
- propõe alocação de capital;
- registra decisões;
- mantém contexto e auditabilidade.

A Editorial Platform deve continuar sendo um sistema independente, responsável por capacidades como:

- publicação;
- apresentação do conteúdo;
- captura de contatos;
- telemetria;
- analytics;
- CMS;
- infraestrutura web;
- experiência do usuário;
- eventualmente exposição de sinais sanitizados.

Não transformar a plataforma no “site do Capital Agent”.

Não transformar o Capital Agent em CMS.

Não compartilhar banco de dados diretamente entre os projetos.

Não criar acoplamento de infraestrutura.

Não criar IAM cross-project desnecessário.

Não fornecer ao Capital Agent credenciais de escrita para produção da plataforma.

---

# 4. Princípios invioláveis

A implementação DEVE preservar todos os princípios abaixo.

## 4.1 Custódia humana

Somente o usuário pode movimentar dinheiro real.

A IA pode:

- pesquisar;
- analisar;
- recomendar;
- preparar instruções;
- registrar estado;
- verificar dados por fontes read-only autorizadas;
- criar artefatos e propostas.

A IA não pode:

- comprar;
- vender;
- transferir;
- sacar;
- pagar;
- movimentar dinheiro;
- obter credenciais de escrita financeira.

## 4.2 Decisões críticas

Toda decisão classificada como crítica continua exigindo autorização humana explícita segundo as regras existentes.

Esta tarefa não pode criar atalhos para:

- publicar em nome do usuário;
- assumir compromissos;
- fazer oferta comercial;
- comunicar-se com cliente;
- gastar dinheiro;
- mudar políticas;
- ampliar autoridade;
- relaxar controles.

## 4.3 Autoevolução

A capacidade de o sistema evoluir a si próprio não pode ser utilizada para aumentar sua própria autoridade ou remover controles.

## 4.4 Auditabilidade

Toda informação economicamente relevante deve manter:

- origem;
- timestamp;
- contexto;
- evidência;
- limitações conhecidas;
- ligação com experimento, decisão ou oportunidade quando aplicável.

## 4.5 Não fabricar precisão

Não inventar métricas, custos, conversões, receitas, valores de tempo, attribution ou dados ausentes.

Se um valor for desconhecido, ele deve permanecer explicitamente desconhecido.

## 4.6 Privacidade

Dados pessoais provenientes da Editorial Platform **não podem ser persistidos no repositório do Capital Agent**.

O Capital Agent deve operar com sinais sanitizados e identificadores pseudônimos.

---

# 5. Escopo obrigatório de implementação

Implemente os seguintes blocos.

---

# 5.1 External Business Data Adapter

Criar uma abstração explícita para entrada de sinais comerciais externos.

Ela deve seguir a filosofia de adapters financeiros read-only já existente.

## Requisitos

O adapter deve ser:

- somente leitura;
- desacoplado de um fornecedor específico;
- idempotente;
- validado por schema;
- observável;
- auditável;
- seguro contra PII;
- capaz de funcionar inicialmente com dados fornecidos por arquivo/fixture/manual import, se a plataforma ainda não possuir API adequada;
- preparado para futura integração read-only com a plataforma sem obrigar implementação dessa integração agora.

Não construir uma integração HTTP artificial apenas para “fechar” a tarefa.

Se a plataforma ainda não tiver interface adequada, implementar o contrato no Capital Agent e registrar a dependência externa no backlog.

## Estrutura conceitual do sinal

O modelo normalizado deve comportar, quando aplicável:

- `signal_id`
- `signal_type`
- `source_system`
- `source_record_id`
- `experiment_id`
- `environment`
- `observed_at`
- `retrieved_at`
- `measurement_period`
- `metric_name`
- `metric_value`
- `unit`
- `data_quality`
- `coverage`
- `attribution_context`
- `evidence_refs`
- `provenance`
- `schema_version`

Não inclua campos que carreguem PII.

Use allowlist de campos sempre que possível.

## Qualidade de evidência

O sistema precisa diferenciar pelo menos:

- dado observado;
- dado agregado;
- dado reportado manualmente;
- dado verificado;
- dado estimado;
- dado indisponível.

Não trate estimativa como fato.

---

# 5.2 Firewall de PII

Implementar proteção explícita para impedir a persistência de dados pessoais da plataforma no Capital Agent.

## O Capital Agent NÃO deve armazenar

Exemplos:

- nome do lead;
- e-mail;
- telefone;
- conteúdo bruto da mensagem;
- endereço;
- identificadores externos que revelem diretamente a identidade;
- dados pessoais desnecessários.

O Capital Agent deve trabalhar com algo semelhante a:

```yaml
lead_id: L-8F3C2A
source: organic
landing_content: post-abc
service_interest: cloud-devops
company_size_band: 11-50
qualification: qualified
commercial_stage: discovery
experiment_id: EXP-001
```

Não use este exemplo cegamente; adapte ao schema real.

## Requisitos técnicos

Criar testes que demonstrem que:

- payloads contendo campos proibidos são rejeitados ou sanitizados de forma determinística;
- logs não imprimem PII;
- fixtures não contêm PII real;
- serialization do estado não reintroduz dados removidos;
- dados comerciais persistidos no Git usam somente campos aprovados.

Preferir allowlist em vez de depender exclusivamente de regex.

---

# 5.3 External Cash Event / External Revenue Receipt

O modelo atual de Human Execution Request foi concebido principalmente para movimentações que o humano executa.

Receita externa é diferente.

Exemplo:

cliente paga uma fatura ou serviço e o dinheiro aparece em uma conta.

O usuário não “executou” o recebimento.

Criar uma abstração própria para isso sem enfraquecer o ledger.

## Requisitos

Criar um modelo equivalente a `ExternalCashEvent` ou nome mais consistente com a arquitetura existente.

Ele deve suportar pelo menos:

- receita;
- reembolso;
- estorno;
- outro influxo externo legítimo, se fizer sentido.

Não usar esse mecanismo para esconder pagamentos ou saídas que continuam exigindo Human Execution Request.

## Estados

Definir uma máquina de estados explícita.

Exemplo conceitual:

```text
OBSERVED
  ↓
REPORTED
  ↓
VERIFIED
  ↓
ATTRIBUTED
  ↓
RECONCILED
  ↓
LEDGER_POSTED
```

Você pode simplificar ou ajustar os nomes, mas preserve a semântica.

## Regra crítica

A IA não pode autoelevar um evento para `VERIFIED` apenas por inferência.

`VERIFIED` deve exigir uma fonte autorizada, por exemplo:

- confirmação humana explícita;
- adapter financeiro read-only confiável;
- outra fonte de verificação que já seja permitida pela política.

## Idempotência

O mesmo recebimento não pode gerar duas entradas de ledger.

Crie chave de idempotência e testes.

## Attribution

O evento deve permitir ligar receita a:

- experimento;
- oportunidade;
- lead pseudônimo;
- publicação;
- campanha;
- origem desconhecida.

`UNKNOWN` é válido.

Nunca force atribuição.

## Ledger

Preserve o ledger append-only.

Não altere as garantias atuais de segurança.

Documente claramente a diferença entre:

- Human Execution Request;
- External Cash Event;
- ledger entry.

---

# 5.4 Schema central de experimento e lifecycle

O projeto precisa ter um schema canônico de experimento.

Analise o modelo atual antes de alterar.

Evite múltiplas representações independentes da mesma informação, como:

- `state`;
- `status`;
- booleanos equivalentes de ativação.

Defina uma única fonte de verdade para o lifecycle.

## Máquina de estados

Use uma máquina explícita semelhante a:

```text
PLANNED
READY_FOR_ACTIVATION
ACTIVE
PAUSED
CLOSED
```

Ajuste se os conceitos existentes exigirem outros estados.

Defina transições permitidas.

Transições inválidas devem falhar.

## Experimentos com zero capital

O schema deve permitir experimentos economicamente válidos com:

```text
capital_budget_brl = 0
```

Exemplo: produzir conteúdo usando uma infraestrutura que já existiria independentemente do experimento.

Isso NÃO significa custo zero absoluto.

O modelo deve distinguir:

### Capital financeiro

- capital alocado;
- custo incremental;
- perda financeira máxima;
- gasto recorrente;
- compromisso financeiro.

### Recursos não financeiros

Quando aplicável:

- tempo humano;
- quantidade de publicações;
- execuções de IA;
- capacidade editorial;
- trabalho operacional.

### Riscos não financeiros

Quando aplicável:

- reputacional;
- privacidade;
- contratual;
- operacional;
- regulatório.

## Regra importante

Não converter automaticamente tempo humano em dinheiro no ledger.

Pode haver:

```text
operator_time_minutes
```

como métrica econômica auxiliar.

Não inventar valor monetário por hora.

## Migração

Migrar EXP-001 e outros experimentos existentes para o novo schema sem perder informação.

Criar migração determinística ou script seguro se necessário.

Não editar histórico de forma que destrua auditabilidade.

---

# 5.5 BUSINESS_SIGNAL

Implementar a entidade `BUSINESS_SIGNAL` prevista conceitualmente pela arquitetura/editorial system.

Ela deve ser distinta de `topic candidate`.

## Semântica

`topic candidate` responde:

> Sobre o que poderíamos escrever?

`BUSINESS_SIGNAL` responde:

> Existe evidência de demanda, necessidade, padrão comercial ou oportunidade de produto/serviço que merece investigação?

## Fontes possíveis

- padrões em leads sanitizados;
- consultas de busca;
- performance de conteúdo;
- perguntas recorrentes;
- comportamento de CTA;
- sinais comerciais externos;
- resultados de experimentos;
- feedback estruturado.

## Requisitos

O sinal deve conter:

- ID estável;
- tipo;
- origem;
- evidências;
- período;
- intensidade/contagem quando conhecida;
- nível de confiança;
- limitações;
- primeira observação;
- última observação;
- status;
- link opcional para oportunidade;
- link opcional para experimento;
- schema version.

Não permitir PII.

## Fluxo

O pipeline deve permitir:

```text
External Business Signal
        ↓
BUSINESS_SIGNAL
        ↓
Opportunity Candidate
        ↓
Evaluation
        ↓
Experiment or rejection
```

Não transformar automaticamente todo BUSINESS_SIGNAL em oportunidade.

A IA deve raciocinar sobre ele.

---

# 5.6 Publication Package + Publication Receipt

Formalizar o handoff editorial entre o Capital Agent e a Editorial Platform.

## Princípio

Antes da publicação:

- o Capital Agent pode manter pesquisa;
- evidências;
- brief;
- draft;
- critic;
- fact-check;
- hipótese de negócio.

Depois da publicação:

- o conteúdo final publicado no CMS/plataforma é a fonte canônica da versão pública;
- o Capital Agent mantém referências e histórico de decisão, não uma fonte concorrente da verdade pública.

## Criar

### Publication Package

Objeto preparado pelo Capital Agent contendo, conforme necessário:

- `publication_request_id`
- `content_brief_id`
- `experiment_id`
- `title`
- `slug_suggestion`
- `draft_ref`
- `fact_check_ref`
- `critic_ref`
- `business_hypothesis_ref`
- `cta_intent`
- `attribution_tags`
- `approval_required`
- `created_at`
- `schema_version`

Não permita que a existência do package implique autorização de publicação.

### Publication Receipt

Objeto de retorno após publicação real.

Exemplo:

- `publication_id`
- `publication_request_id`
- `platform_content_id`
- `canonical_slug`
- `canonical_url` ou referência equivalente
- `published_at`
- `environment`
- `campaign_id`
- `verification_source`
- `schema_version`

Se a plataforma ainda não produzir esse receipt, implementar o schema e ingestão no Capital Agent e criar item P0 no backlog da plataforma.

## Segurança

O Capital Agent NÃO deve nesta sessão:

- publicar diretamente;
- chamar endpoint de escrita do CMS;
- receber token administrativo;
- executar deploy;
- mergear código da plataforma.

---

# 5.7 Métricas experimentais com proveniência

Criar ou reforçar um modelo canônico para observações de métricas.

Cada observação economicamente relevante deve carregar contexto suficiente para evitar números sem origem.

Campos relevantes:

- experimento;
- métrica;
- valor;
- unidade;
- período;
- source;
- environment;
- retrieved_at;
- coverage;
- data_quality;
- limitations;
- schema_version.

## Ambientes

Dados de:

- `dev`;
- testes;
- smoke tests;
- synthetic monitoring;
- E2E;
- tráfego administrativo;

não devem contaminar métricas econômicas de produção.

Se a plataforma ainda não fornecer os marcadores necessários para excluir esse tráfego, registrar dependência P0/P1 no backlog.

Somente dados de produção, após a activation date do experimento e com origem válida, devem contribuir para avaliação econômica oficial.

---

# 5.8 Triggers determinísticos de negócio

Estender o scheduler/configuração com triggers determinísticos quando fizer sentido para a arquitetura atual.

Candidatos:

- `new_business_signal_detected`
- `new_qualified_lead_detected`
- `experiment_metric_threshold_reached`
- `platform_signal_source_stale`
- `measurement_window_completed`
- `attribution_pending_too_long`
- `content_performance_anomaly`

Não é obrigatório usar exatamente esses nomes.

## Regra

A detecção do fato deve ser determinística.

Exemplo:

```text
qualified_leads mudou de 2 para 3
```

é lógica determinística.

A pergunta:

```text
esses leads indicam oportunidade de criar um novo serviço?
```

é trabalho cognitivo da IA.

Não coloque LLM dentro de trigger determinístico desnecessariamente.

---

# 5.9 Comparação contra alternativas / proteção contra viés da plataforma

O Capital Agent não deve favorecer EXP-001 apenas porque a plataforma já existe.

Incorpore à revisão periódica de alocação uma comparação explícita entre:

1. EXP-001 ou melhor experimento baseado na plataforma;
2. melhor oportunidade financeira disponível;
3. melhor oportunidade de negócio não relacionada à plataforma;
4. benchmark / do nothing.

Considere, conforme os modelos existentes:

- capital requerido;
- downside;
- qualidade de evidência;
- tempo para feedback;
- reversibilidade;
- carga operacional;
- escalabilidade;
- complexidade;
- risco;
- retorno potencial;
- custo de oportunidade.

Não fabrique uma alternativa inexistente.

Se não houver oportunidade válida em uma categoria, registre `NONE_AVAILABLE` ou equivalente.

---

# 5.10 Definição do mecanismo econômico inicial de EXP-001

Reestruture EXP-001 para representar de forma estreita o mecanismo inicial de teste.

Não tente provar simultaneamente:

- ads;
- afiliados;
- produtos digitais;
- consultoria;
- newsletter;
- SEO;
- múltiplos canais de monetização.

A primeira hipótese deve ser suficientemente estreita para gerar aprendizado causal razoável.

O funil recomendado, salvo evidência melhor no repositório, é:

```text
conteúdo relevante
    ↓
tráfego qualificado
    ↓
CTA
    ↓
lead
    ↓
lead qualificado
    ↓
conversa/proposta
    ↓
receita atribuível
```

Métricas de topo de funil, como impressões e sessões, são diagnósticas.

As métricas econômicas prioritárias devem se aproximar de:

- qualified leads;
- proposals;
- attributable revenue;
- incremental cost;
- profit;
- ROIC quando matematicamente aplicável.

Se `capital_deployed = 0`, não produzir ROIC infinito nem dividir por zero.

Nesse caso use métricas economicamente significativas alternativas e documente a limitação.

---

# 6. Backlog obrigatório para dependências da Editorial Platform

Você está proibida de modificar o repositório da plataforma.

Entretanto, deve inspecioná-lo o suficiente para descobrir quais capacidades já existem e quais ainda faltam.

Use o mecanismo de backlog existente no Capital Agent.

Se não houver um mecanismo canônico adequado, crie:

```text
backlog/platform-integration.md
```

ou estrutura equivalente consistente com o repositório.

## Cada item deve conter

- ID;
- título;
- prioridade;
- status;
- target repository;
- owner sugerido: `Editorial Platform AI`;
- motivo;
- dependência do Capital Agent;
- contrato esperado;
- campos;
- regras de segurança;
- privacidade;
- exemplos;
- critérios de aceite;
- condição que desbloqueia o Capital Agent;
- links para schemas do Capital Agent quando existirem.

## Prioridades

Use:

- `P0` = bloqueia ativação correta/segura do EXP-001;
- `P1` = necessário para avaliação confiável ou automação relevante;
- `P2` = melhoria posterior;
- `P3` = opcional.

## Itens que você deve avaliar explicitamente

### P0/P1 — Telemetria sanitizada

A plataforma precisa conseguir fornecer sinais como:

- conteúdo;
- sessão agregada;
- CTA;
- lead sanitizado;
- estágio comercial;
- conversão;
- receita atribuível ou referência para reconciliação.

Não exigir que a plataforma exponha PII ao Capital Agent.

### P0 — Attribution

Avaliar necessidade de capturar:

- landing page;
- article/content ID;
- CTA ID;
- referrer;
- campaign;
- UTM;
- first touch;
- last touch;
- environment;
- timestamp;
- referenceId.

### P0 — Publication Receipt

A plataforma precisa conseguir devolver evidência de publicação real.

### P0/P1 — Separação de tráfego

A plataforma precisa permitir distinguir:

- produção;
- dev;
- synthetic;
- smoke;
- E2E;
- admin/internal.

### P1 — Lead lifecycle sanitizado

O Capital Agent deve conseguir receber estados comerciais sem receber identidade.

Exemplo:

```text
new
qualified
discovery
proposal
won
lost
```

### P1 — Data quality / coverage

Analytics deve declarar cobertura e limitações, especialmente quando depender de consentimento.

### P2 — PR-only automation

Somente considerar futuramente.

Se for implementado um bot para código da plataforma, ele deve:

- abrir PR;
- não mergear;
- não fazer deploy de produção;
- não receber permissões administrativas desnecessárias.

Não implementar isso agora.

---

# 7. O que NÃO fazer

Não faça nenhuma das ações abaixo:

- não alterar o repositório da Editorial Platform;
- não fazer deploy;
- não publicar conteúdo;
- não criar domínio;
- não alterar DNS;
- não mexer em CloudFront;
- não alterar AWS da plataforma;
- não criar credenciais;
- não criar secrets;
- não integrar banco a banco;
- não implementar CRM completo;
- não implementar uma API grande sem necessidade;
- não criar EventBridge ou outro bus central apenas por arquitetura futura;
- não substituir o scheduler determinístico por LLM;
- não relaxar policy;
- não remover Human Execution Request;
- não permitir que AI confirme execução financeira;
- não marcar receita como verificada por inferência;
- não armazenar PII;
- não monetizar tempo humano automaticamente;
- não transformar EXP-001 na missão principal do Capital Agent;
- não criar um segundo cérebro editorial na plataforma;
- não alterar comportamento sem teste;
- não reescrever o projeto inteiro.

---

# 8. Compatibilidade e migração

Toda mudança deve ser backward-aware.

## Obrigatório

Antes de modificar schema ou arquivos persistidos:

1. localize todas as leituras e escritas;
2. localize fixtures;
3. localize testes;
4. localize geração de estado;
5. localize validações;
6. localize documentação que descreve o formato;
7. localize scheduler/triggers que dependem dele.

Depois:

- implemente migração;
- atualize testes;
- atualize documentação;
- preserve histórico;
- evite alterações manuais silenciosas.

Se houver versionamento de schema, utilize-o.

Se não houver, introduza versionamento somente onde ele realmente agrega segurança.

---

# 9. Testes obrigatórios

Adicione testes unitários e de integração suficientes para demonstrar, no mínimo:

## Experimentos

- experimento com `capital_budget_brl = 0` é válido;
- transição válida funciona;
- transição inválida falha;
- estado redundante não diverge;
- EXP-001 migra corretamente;
- métricas dev não entram na avaliação oficial;
- métricas anteriores à activation date não entram na avaliação oficial.

## PII

- payload com PII é rejeitado ou sanitizado segundo o contrato;
- dado persistido não contém PII;
- logs não vazam PII;
- schema usa allowlist;
- fixtures não usam dados pessoais reais.

## Business Adapter

- ingestão é idempotente;
- provenance é obrigatória;
- source/environment são preservados;
- malformed payload falha de forma segura;
- dado estimado não vira verificado.

## External Cash Event

- IA não consegue auto-verificar receita;
- evento não verificado não entra no ledger;
- evento verificado pode avançar;
- evento duplicado não duplica ledger;
- attribution pode ser `UNKNOWN`;
- entradas externas não exigem falsamente Human Execution Request;
- saídas continuam exigindo o fluxo financeiro existente.

## BUSINESS_SIGNAL

- topic candidate não é confundido com business signal;
- sinal sem evidência suficiente não vira automaticamente oportunidade;
- business signal não contém PII;
- sinal mantém provenance.

## Publication

- publication package não significa published;
- publication receipt exige identificação externa suficiente;
- receipt duplicado é idempotente;
- publicação continua exigindo autorização conforme policy.

## Scheduler

- triggers novos são determinísticos;
- ausência de fonte não inventa job;
- fonte stale gera estado/trabalho apropriado;
- scheduler não chama LLM para detectar mudança simples.

## Regressão

- todos os testes existentes continuam passando;
- ledger continua append-only;
- critical decisions continuam protegidas;
- state generation continua consistente;
- critic e multi-provider behavior não são quebrados.

---

# 10. Documentação obrigatória

Atualize os documentos canônicos relevantes.

No mínimo, documente:

1. arquitetura da integração com sistemas externos;
2. diferença entre `Human Execution Request` e `External Cash Event`;
3. modelo de experimento zero-capital;
4. resource budgets;
5. riscos não financeiros;
6. BUSINESS_SIGNAL;
7. publication package/receipt;
8. privacidade e PII;
9. provenance de métricas;
10. separação dev/prod/test;
11. regras de attribution;
12. backlog da plataforma;
13. critérios para ativar EXP-001.

Evite duplicar a mesma regra em cinco documentos.

Se houver um documento canônico claro, coloque a definição completa nele e use referências nos demais.

Atualize `START_HERE.md` ou documento equivalente apenas se necessário para que uma nova IA reconstrua corretamente o contexto.

---

# 11. Critérios para EXP-001 ficar READY_FOR_ACTIVATION

Não marque EXP-001 como ACTIVE nesta sessão.

No máximo, deixe-o `READY_FOR_ACTIVATION` se todas as pré-condições forem satisfeitas.

A ativação real continua dependendo do humano.

Antes de `READY_FOR_ACTIVATION`, confirme que existem:

- hipótese explícita;
- success metric;
- failure criteria;
- kill condition;
- measurement window;
- attribution model;
- definição de qualified lead;
- definição de revenue attribution;
- resource budget;
- capital budget;
- incremental cost policy;
- privacy policy aplicável;
- fonte de métricas;
- separação dev/prod;
- lead capture funcional;
- publication handoff;
- external revenue reconciliation;
- nenhuma dependência P0 aberta.

Se houver qualquer dependência P0 da plataforma, mantenha EXP-001 em estado anterior apropriado e registre exatamente o que falta.

---

# 12. Ordem recomendada de execução

Execute nesta ordem, salvo dependência técnica real:

## Fase A — Discovery

1. ler documentos canônicos;
2. mapear código;
3. mapear schemas;
4. mapear estado;
5. mapear scheduler;
6. mapear ledger;
7. mapear EXP-001;
8. inspecionar Editorial Platform somente leitura;
9. produzir uma matriz curta:
   - já existe;
   - existe parcialmente;
   - falta;
   - depende da plataforma.

Não pare após essa matriz.

## Fase B — Núcleo de dados

1. experiment schema/lifecycle;
2. metric observation/provenance;
3. business signal;
4. external cash event;
5. publication package/receipt;
6. business adapter.

## Fase C — Políticas e enforcement

1. PII firewall;
2. verification rules;
3. idempotency;
4. environment filtering;
5. attribution rules;
6. state transition validation.

## Fase D — Scheduler

Adicionar triggers determinísticos somente depois de os modelos estarem estáveis.

## Fase E — EXP-001

Migrar e estreitar EXP-001.

## Fase F — Backlog externo

Registrar tudo que depende da Editorial Platform.

## Fase G — Docs + testes + auditoria

Executar suite completa, revisar documentação e fazer auditoria de consistência.

---

# 13. Auditoria final obrigatória

Ao terminar, faça uma auditoria explícita.

Verifique:

## Segurança

- nenhuma permissão financeira foi ampliada;
- nenhuma critical decision foi removida;
- nenhum write access externo foi criado;
- nenhuma credencial foi adicionada;
- nenhuma PII foi persistida.

## Arquitetura

- Capital Agent continua independente da plataforma;
- Editorial Platform continua independente do Capital Agent;
- não há banco compartilhado;
- integração é por contratos;
- external business adapter é read-only;
- receipt não equivale a autorização.

## Dados

- schemas são versionáveis;
- eventos são idempotentes;
- provenance existe;
- environment existe;
- métricas não têm ambiguidade entre dev e prod;
- revenue verification é distinta de inference.

## Experimentos

- zero-capital funciona;
- resource budget existe;
- risk model existe;
- lifecycle é único;
- EXP-001 não foi ativado automaticamente.

## Documentação

- regras canônicas não se contradizem;
- backlog externo está priorizado;
- uma nova IA consegue entender a arquitetura lendo os documentos principais.

---

# 14. Saída final da sessão

Depois de implementar, responda com um relatório objetivo contendo:

## 1. Mudanças realizadas

Lista por domínio:

- schemas;
- código;
- scheduler;
- policies;
- tests;
- docs;
- EXP-001;
- backlog.

## 2. Arquivos alterados

Liste arquivos criados, alterados e removidos.

## 3. Migrações

Explique qualquer migração de estado/schema.

## 4. Testes

Informe:

- comandos executados;
- resultado;
- testes novos;
- falhas restantes, se houver.

## 5. Dependências da Editorial Platform

Liste por prioridade:

```text
P0
P1
P2
P3
```

Cada item deve informar:

- por que existe;
- o que a outra IA deve implementar;
- contrato;
- critérios de aceite;
- como o Capital Agent saberá que foi desbloqueado.

## 6. EXP-001

Informe seu estado final e justifique.

Não o marque `ACTIVE` sem autorização humana.

## 7. Riscos restantes

Apenas riscos reais.

Não invente “melhorias futuras” genéricas para preencher seção.

## 8. Verificação de escopo

Declare explicitamente:

- se o repositório da Editorial Platform permaneceu sem alterações;
- se nenhum deploy foi executado;
- se nenhuma movimentação financeira foi realizada;
- se nenhuma política crítica foi relaxada.

---

# 15. Definition of Done

A tarefa só está concluída quando:

- [ ] o Capital Agent possui contrato explícito de sinais comerciais externos;
- [ ] existe proteção contra PII;
- [ ] existe caminho formal para receita externa;
- [ ] o ledger continua seguro;
- [ ] experimentos zero-capital são suportados;
- [ ] há lifecycle canônico de experimento;
- [ ] BUSINESS_SIGNAL está implementado;
- [ ] publication package/receipt estão modelados;
- [ ] métricas possuem provenance;
- [ ] dev/test não contaminam avaliação econômica;
- [ ] triggers de negócio relevantes são determinísticos;
- [ ] EXP-001 foi migrado;
- [ ] EXP-001 continua não ativo sem autorização;
- [ ] dependências da plataforma estão registradas e priorizadas;
- [ ] nenhuma mudança foi feita no repositório da plataforma;
- [ ] documentação canônica foi atualizada;
- [ ] testes novos foram adicionados;
- [ ] testes existentes continuam passando;
- [ ] auditoria final foi concluída.

---

# 16. Princípio de decisão durante a implementação

Sempre que houver dúvida entre:

```text
mais automação
```

e

```text
mais controle/auditabilidade
```

prefira controle e auditabilidade, a menos que a política canônica permita explicitamente a automação.

Sempre que houver dúvida entre:

```text
acoplamento direto
```

e

```text
contrato explícito
```

prefira contrato explícito.

Sempre que houver dúvida entre:

```text
guardar dado bruto
```

e

```text
guardar somente o sinal necessário
```

prefira o sinal mínimo necessário.

Sempre que houver dúvida entre:

```text
assumir que algo aconteceu
```

e

```text
esperar evidência verificável
```

espere evidência verificável.

O objetivo não é tornar o sistema apenas mais sofisticado.

O objetivo é permitir que o Capital Agent opere experimentos de negócio reais — incluindo a Editorial Platform — mantendo **custódia humana, segurança, independência entre sistemas, privacidade, evidência, rastreabilidade e capacidade de aprender economicamente com resultados reais**.
