# Publication Log

Registro narrativo do andamento do projeto Capital Agent, mantido
especificamente para alimentar uma publicação ou série de publicações sobre
o projeto (ex.: posts de blog, série documentando "IA operando um
experimento de capital"). Não é fonte de governança nem estado operacional
— para isso, ver `journal/decisions/`, `journal/system_changes/`,
`data/ledger.csv` e `context/CURRENT_STATE.md`, que continuam sendo as
fontes canônicas.

Este arquivo existe para não misturar propósito com `CLAUDE.md` (que é só
um adaptador fino, sem conteúdo de estado ou narrativa) nem com os registros
operacionais (que são formais/auditáveis, não narrativos). Este arquivo é
prosa deliberadamente mais solta — histórias, decisões marcantes, reviravoltas,
citações reais da conversa — pensada para ser lida e reaproveitada como
matéria-prima editorial, não como registro de compliance.

## Protocolo de atualização

- Adicionar uma entrada ao final de sessões com conteúdo narrativamente
  relevante (decisão importante, reviravolta, erro real e correção,
  aprendizado, marco do projeto). Não é preciso registrar toda sessão —
  sessões puramente mecânicas/sem fato novo não precisam de entrada.
  Sessões extensas com o mesmo tema (ex: esta primeira) podem gerar uma
  única entrada consolidada em vez de uma por decisão.
- Cada entrada deve linkar para os registros canônicos relevantes
  (`journal/decisions/DEC-...`, `journal/system_changes/SYS-...`,
  `approvals/archive/APR-...`) em vez de duplicar o conteúdo técnico
  completo — aqui é o "porquê importa" e "como aconteceu", não o pacote de
  aprovação inteiro.
- Formato de entrada: data, título curto, corpo em prosa. Ordem
  cronológica (mais antiga primeiro), já que é uma narrativa, não um índice
  de busca.
- Este arquivo nunca é lido automaticamente por padrão no início de uma
  sessão operacional (ao contrário de `START_HERE.md`) — é consultado sob
  demanda, quando o objetivo da sessão é trabalhar em conteúdo/publicação.

## Entradas

### 2026-08-10 — O nascimento do Capital Agent: de zero a primeira transação real

O projeto começou como um esqueleto: um repositório com BRL 1.000,00 de
capital inicial, uma política de investimento no papel e um punhado de
templates vazios. Não havia contexto persistente entre sessões, não havia
mecanismo de agendamento, não havia sequer uma regra explícita dizendo que
a IA nunca poderia tocar em dinheiro de verdade — isso estava implícito,
mas não *garantido em código*.

O primeiro grande movimento foi construir o **Context Management System**:
`START_HERE.md`, `CONTEXT_MANAGEMENT.md`, e uma estrutura de `context/`
capaz de reconstruir o estado inteiro do projeto para qualquer IA nova, sem
depender de memória de conversa anterior. Isso incluiu `context/CURRENT_STATE.md`,
gerado deterministicamente a partir do próprio ledger — nunca escrito à
mão, nunca inventado.

Depois veio a decisão arquitetural mais importante do projeto: formalizar o
**invariante de custódia**. A regra é simples de dizer e difícil de garantir
de verdade: *só o dono humano pode mover dinheiro real*. Nenhuma IA, script
ou agendador jamais teria capacidade de executar uma operação financeira.
Isso não ficou só na prosa — foi implementado como guarda de código
(`load_policy()` recusa carregar se a flag de execução autônoma for
verdadeira), como um lifecycle inteiro de "Human Execution Request"
(`execution/human_requests/`), e como testes automatizados garantindo que
nenhuma transação pudesse ser marcada como executada sem confirmação humana
explícita.

Uma auditoria de prontidão da Phase 0 encontrou dois furos reais nessa
garantia antes que importassem de verdade: o comando `record` permitia
lançar uma "compra" no ledger diretamente, contornando todo o fluxo de
aprovação; e a proposta de mudança de sistema só rejeitava execução
autônoma se quem propusesse marcasse a flag honestamente — sem verificação
independente. Os dois foram fechados no mesmo ciclo em que foram
encontrados (`SYS-20260810-F9CEAA`).

O sistema ganhou um **agendador determinístico** (`src/scheduler.py`),
registrado de verdade no Windows Task Scheduler, rodando a cada 15 minutos
— decidindo sozinho se há trabalho cognitivo real antes de sequer cogitar
chamar uma IA. E ganhou sua primeira integração externa: o MCP do Yahoo
Finance, instalado só depois de passar pelo mesmo processo formal de
aprovação crítica que qualquer decisão de capital passaria — incluindo uma
avaliação honesta do risco de rodar código de terceiro não auditado.

O primeiro ciclo real de pesquisa de oportunidades comparou ações/cripto
contra Tesouro Selic contra modelos de negócio digitais — e rejeitou
picking de ações não por preferência, mas por matemática: com teto de
BRL 100 por posição, custo de transação come qualquer aposta pequena
demais para diversificar de verdade.

A primeira proposta de negócio — uma oferta de consultoria paga — foi morta
não por falta de mercado, mas por não caber no mandato: o dono do projeto
deixou claro que consultoria pessoal significaria exatamente o tipo de
intervenção contínua que ele queria minimizar. Isso virou uma lição
registrada (`context/knowledge/lessons.md`): checar todo modelo de negócio
contra "quem faz o trabalho contínuo", não só contra política e capital.

A segunda tentativa — empacotar o trabalho técnico de outro projeto do
dono como produto — também não vingou: o projeto-fonte não estava pronto,
e o dono pediu para começar do zero, sem depender dele. Uma terceira ideia
(um kit genérico de governança de agentes de IA) foi pesquisada e
descartada em minutos: o espaço já tem concorrentes gratuitos e bem
financiados (Microsoft, Galileo, NVIDIA, Meta). Matar uma ideia fraca na
fase de pesquisa, antes de gastar esforço real de construção, é
exatamente o comportamento que o processo foi desenhado para produzir.

E então veio o primeiro dinheiro de verdade. A primeira tentativa (Tesouro
Selic, BRL 100) esbarrou em um problema mecânico banal e revelador: o
sistema achava que ia zerar o próprio patrimônio contabilizado assim que
o dinheiro saísse do caixa para virar um título — um furo de contabilidade
descoberto só ao tentar executar de verdade, não em teoria (`SYS-20260810-E87857`).
Depois veio uma confusão de print (Tesouro Prefixado 2032 em vez de Selic),
corrigida ao ser questionada. E por fim, um limite de política genuíno:
o lote mínimo real do Tesouro Selic (BRL 196,64) era maior que o teto de
alocação única então vigente (BRL 100) — o que forçou uma mudança de
política formal, proposta, avaliada e só então aprovada explicitamente pelo
dono do projeto (`SYS-20260810-EBED61`).

Em 10/08/2026, às 15h55, BRL 195,65 saíram do caixa do experimento e
viraram Tesouro Selic 2031 de verdade, na conta de corretora do dono do
projeto. A IA recomendou, preparou e registrou cada etapa. O dono do
projeto foi o único que efetivamente apertou o botão. Nenhuma linha de
código jamais teve capacidade de fazer isso sozinha — essa era a promessa
desde o primeiro invariante escrito neste projeto, e ela se sustentou na
primeira vez em que importou de verdade.

Referências: `journal/decisions/DEC-20260810-A032A0.md`,
`journal/decisions/DEC-20260810-875930.md`,
`journal/decisions/DEC-20260810-451C32.md`,
`journal/system_changes/SYS-20260810-BD6581.md`,
`journal/system_changes/SYS-20260810-F9CEAA.md`,
`journal/system_changes/SYS-20260810-E87857.md`,
`journal/system_changes/SYS-20260810-EBED61.md`,
`approvals/archive/APR-20260810-FDD418.md`,
`execution/human_requests/completed/HER-20260810-544DBF.json`.

### 2026-08-10 (continuação) — Três ideias mortas, e um erro de método descoberto por repetição

Com o dinheiro de fato investido e o registro de história criado, a busca
pelo vetor de crescimento continuou — e tropeçou três vezes seguidas do
mesmo jeito, o que acabou sendo o achado mais interessante da sessão.

A primeira ideia (kit genérico de governança de agentes de IA) já tinha
caído antes, derrubada por concorrentes gratuitos de peso (Microsoft,
NVIDIA, Meta). A busca continuou com duas outras: uma planilha de controle
financeiro brasileira — categoria real e vendável (o mercado de
infoprodutos no Hotmart já passou de R$30 bilhões em volume histórico),
mas um nicho tão comum entre iniciantes que a primeira busca já trouxe um
concorrente estabelecido vendendo exatamente a mesma coisa. E uma
calculadora de imposto de renda sobre ganho de capital em investimentos —
essa parecia mais forte por aproveitar uma capacidade real já demonstrada
neste próprio projeto (lógica de ledger e categorização fiscal), mas
esbarrou em algo pior que concorrência comercial: uma ferramenta gratuita
oficial da Receita Federal em parceria com a B3, a calculadora "ReVar".

As três ideias morreram na fase de pesquisa, sem nenhum esforço de
construção gasto — exatamente onde uma ideia fraca deve morrer. Mas a
repetição revelou o problema de verdade: as três vieram de buscas
genéricas tipo "melhores ideias de [categoria]" — e qualquer coisa fácil o
bastante para aparecer numa busca de dois segundos já foi encontrada e
ocupada por alguém antes. Esse padrão foi registrado formalmente em
`context/knowledge/recurring-errors.md` como um erro de método, não de
execução: bom para confirmar que uma categoria existe, ruim para achar uma
brecha real dentro dela.

O próximo passo, ainda em aberto ao fim desta sessão, é mudar de método:
procurar reclamações específicas e recorrentes em vez de listas prontas —
mais lento, mas é o que de fato separa uma ideia vazia de uma com mercado
real por trás.

Referências: `context/knowledge/rejected-opportunities.md`,
`context/knowledge/recurring-errors.md`.

### 2026-08-10 (continuação) — Um candidato sobrevive à pesquisa, pela primeira vez

Mudar o método valeu a pena rápido. Em vez de buscar "melhores ideias",
a pesquisa passou a procurar reclamações e eventos reais — e esbarrou em
algo genuinamente diferente das três tentativas anteriores: a partir de
2026, autônomos no Brasil passaram a ser obrigados a emitir NFS-e pelo
emissor nacional, e a confusão em torno disso é real e atual, não um nicho
já minerado por todo mundo. Uma segunda busca, mais funda, revelou que a
aposta era mais séria do que parecia: um MEI que não emite a nota quando
obrigado pode ter o CNPJ cancelado e multa de até 75% do valor da operação
— não os 5% que uma primeira busca mais superficial tinha sugerido.
Números como esse não se aceitam de primeira; a segunda busca é que trouxe
o valor certo.

Isso trouxe uma pausa deliberada, não uma corrida adiante: um erro nessa
ferramenta teria consequência financeira real para quem confiasse nela.
A decisão de continuar mesmo assim não foi minha sozinha — foi trazida
explicitamente para o dono do projeto, que autorizou seguir "com cautela".
O desenho que resultou disso segue o mesmo princípio que já rege o projeto
inteiro desde o primeiro dia: a ferramenta nunca executa nada em nome de
ninguém (nunca emite a nota, nunca dá classificação fiscal definitiva),
só organiza e explica — o mesmo invariante de custódia, agora aplicado a
obrigação fiscal em vez de dinheiro.

A checagem de concorrência (via leitura direta de um post comparativo,
não só busca) mostrou algo interessante: as ferramentas comerciais
existentes (Vimbo e afins) são pensadas para "gestores de todos os
portes", com integração bancária e múltiplos usuários — pesadas demais
para quem é MEI sozinho e só quer entender o que precisa fazer. A própria
fonte comercial admite que os emissores públicos "carecem de interface
amigável" para autônomos menos técnicos. Nenhum concorrente apareceu
mirando especificamente esse público, com essa simplicidade.

Primeiro passo real, ainda não feito: verificar cada fato direto na fonte
oficial (gov.br/Receita Federal), não em posts de blog secundários, antes
de escrever qualquer linha do guia.

Referências: `journal/decisions/DEC-20260810-C5EA4F.md`.

### 2026-08-10 (continuação) — Antes de continuar, uma pergunta sobre aprender com o processo

O dono do projeto interrompeu a pesquisa com uma pergunta que não era
sobre a ideia de negócio, era sobre o processo em si: "temos alguma
maneira de aprender no processo, qual quer que seja ele? você acabou de
tomar decisões importantes e mudar a rota. isso melhorou o resultado."

A resposta honesta foi "parcialmente". Os arquivos de conhecimento
(`context/knowledge/`) já existiam e já tinham capturado os aprendizados
da sessão em tempo real — mas nada obrigava consultá-los antes de começar
de novo. Era perfeitamente possível repetir o mesmo erro pela quarta vez.
Isso virou uma correção real e pequena: um comando (`knowledge-check`) que
imprime os três arquivos relevantes de uma vez, e uma exigência explícita
no manual de operação para rodá-lo antes de qualquer nova pesquisa de
oportunidade. Não é travado por código — seria possível pular mesmo assim
— mas agora é uma linha de comando em vez de uma desculpa de "esqueci de
olhar três arquivos".

Só depois disso a pesquisa do NFS-e continuou. A verificação em fonte
primária (não mais busca genérica, agora leitura direta do gov.br e da Lei
Complementar 123/2006) confirmou o núcleo da regra do MEI e revelou algo
que nenhuma fonte secundária mencionou: a penalidade por não emitir NFS-e
provavelmente não é um número nacional único — é matéria municipal, porque
a NFS-e documenta o ISS, um imposto de competência do município. Os
números de "5%" ou "75%" que circulam por aí provavelmente vieram da
legislação de uma cidade específica, citados sem esse contexto. É provável
que o próprio conteúdo concorrente esteja errado nesse ponto — o que, se
verdade, é exatamente a diferenciação que faltava.

Referências: `journal/system_changes/SYS-20260810-A54ECC.md`,
`journal/decisions/DEC-20260810-C5EA4F.md` (Addendums 2 e 3),
`experiments/drafts/nfse-mei-guide-outline.md`.
