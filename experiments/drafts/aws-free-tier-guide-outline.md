# Rascunho — Página "AWS Free Tier mudou: o que ninguém te contou sobre o plano Free"

Status: **esboço, não conteúdo final, não publicado**. Ligado a
`journal/decisions/DEC-20260810-7B41E9.md`. Canal: página dedicada e
independente (não o blog — ainda não pronto para conteúdo real, ver
Addendum 3), hospedagem a definir. Publicação de qualquer versão final é
decisão crítica separada (identidade/representação pública), ainda não
solicitada.

## Premissa de escopo (não negociável)

- Conteúdo técnico/organizacional puro — nenhuma classificação fiscal ou
  jurídica envolvida (diferente do candidato NFS-e).
- Todo número, prazo ou comportamento citado precisa estar verificado
  direto na documentação oficial da AWS (`docs.aws.amazon.com`,
  `aws.amazon.com/free`), nunca só em blog secundário.
- Deixar explícito, logo no início, que termos da AWS podem mudar sem
  aviso e que o leitor deve confirmar na documentação oficial antes de
  agir — mesmo princípio de "verificado em [data], confirme na fonte" do
  candidato NFS-e, adaptado para um tema técnico em vez de fiscal.
- A página nunca promete monitorar a conta da AWS do leitor nem substitui
  os alertas oficiais da própria AWS — só organiza e explica o que a
  documentação da AWS deixa espalhado e, em um ponto específico,
  contraditório.

## Gancho central

A AWS tem duas páginas oficiais que, lidas isoladamente, dão respostas
diferentes sobre o que acontece quando o plano Free acaba:

- `avoid-charges-after-free-tier.html` (mais genérica, fácil de achar):
  soa como "você só passa a ser cobrado pelo uso".
- `free-tier-plans.html` (mais específica, sobre o plano Free pós-jul/2025):
  diz que a conta **fecha automaticamente** e você **perde acesso aos
  dados**, com 90 dias de retenção antes da exclusão permanente.

A AWS não conecta as duas páginas. Esse é o ponto de maior risco de
confusão real encontrado na pesquisa — e o diferencial da página em
relação ao único concorrente em português encontrado (unicast.com.br, que
cobre bem a mudança de política mas não cobre esse comportamento).

## Esboço de seções

1. **Isso te afeta?** — checklist rápido: você criou (ou vai criar) uma
   conta AWS a partir de 15/07/2025? Se sim, está no modelo de créditos
   (plano Free), não no antigo modelo de 12 meses grátis.
2. **Os dois modelos, sem misturar** — tabela lado a lado:
   - Contas antigas (antes de 15/07/2025): 12 meses grátis, limites fixos
     por serviço (ex.: 5 GB S3, 750h EC2 t2/t3.micro por mês), uso acima
     do limite é cobrado à tarifa normal, sem acumular saldo não usado.
   - Contas novas (a partir de 15/07/2025): US$100 de crédito + até
     US$100 extra por atividades de onboarding (até US$200), válidos por
     6 meses ou até acabar o crédito, o que vier primeiro.
3. **O que "Always Free" ainda cobre, nos dois casos** — 30+ serviços com
   limite mensal grátis, independente do plano (Free ou Paid) e
   independente do crédito ter acabado.
4. **O ponto que a maioria do conteúdo em português não cobre: o que
   acontece quando os 6 meses ou o crédito acabam** — a conta do plano
   Free fecha automaticamente, recursos param, acesso aos dados é
   perdido; AWS retém o conteúdo por 90 dias antes de excluir
   permanentemente; dá para fazer upgrade para o plano Paid dentro desses
   90 dias para recuperar o acesso (créditos restantes, se houver, são
   aplicados à fatura seguinte).
5. **A contradição nas próprias páginas da AWS** — seção dedicada
   explicando as duas páginas oficiais e por que confiar só na mais
   genérica (`avoid-charges-after-free-tier.html`) pode enganar quem está
   no plano Free.
6. **Checklist prático antes do prazo acabar** — acompanhar o saldo de
   crédito e a data limite pelo AWS Billing and Cost Management console;
   os avisos automáticos da AWS chegam em 50%/25%/10% de crédito restante
   e 15/7/2 dias antes do prazo, mas não confiar só neles; decidir com
   antecedência entre fazer upgrade para Paid ou exportar/desligar
   recursos antes do fechamento automático.
7. **Onde conferir a informação oficial e atualizada** — links diretos
   para `aws.amazon.com/free`, `aws.amazon.com/free/legacy/free-tier-faqs`
   e a documentação de billing, com a data em que cada uma foi consultada
   nesta pesquisa, deixando claro que a AWS pode alterar isso sem aviso.

## Fontes já verificadas nesta pesquisa (a citar na página)

- `aws.amazon.com/free` — estrutura atual do plano Free/Paid, valores de
  crédito, serviços Always Free.
- `aws.amazon.com/free/legacy/free-tier-faqs` — regras do modelo antigo de
  12 meses para contas anteriores a 15/07/2025.
- `docs.aws.amazon.com/awsaccountbilling/.../free-tier-plans.html` —
  comparação oficial Free vs. Paid, comportamento de fechamento automático
  de conta e retenção de 90 dias.
- `docs.aws.amazon.com/awsaccountbilling/.../avoid-charges-after-free-tier.html`
  — página que, lida isoladamente, não menciona perda de dados; citada
  explicitamente na página como o ponto de confusão a evitar, não só como
  fonte de apoio.

## Pendente antes de qualquer versão final

- Redigir o conteúdo completo de cada seção (esta é só a estrutura).
- Definir o mecanismo de validação de interesse a embutir na página (ex.:
  captura de e-mail ou contagem simples de "isso foi útil"), já que o
  candidato foi desenhado para servir também como teste barato de
  interesse, não só como entrega de conteúdo.
- Definir onde a página vai rodar (hospedagem/domínio) — decisão do dono
  do projeto, não resolvida ainda (Addendum 3 da decisão).
- Revisão do dono do projeto antes de qualquer publicação (gate crítico já
  identificado em `DEC-20260810-7B41E9.md`).
