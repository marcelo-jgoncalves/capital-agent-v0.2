# AWS Free Tier mudou: o que a própria AWS não deixa claro sobre o plano Free

*Guia rápido para quem tem (ou vai criar) uma conta AWS pequena — projeto
pessoal, side project, time pequeno — e não quer ser pego de surpresa.*

> **Isto não monitora sua conta AWS por você e não substitui os avisos
> oficiais da AWS.** É um guia organizacional que reúne e explica, em
> linguagem simples, o que está espalhado (e em um ponto, contraditório)
> na documentação oficial da AWS. Termos podem mudar sem aviso — confirme
> sempre em [aws.amazon.com/free](https://aws.amazon.com/free) antes de
> agir. Este guia não é conteúdo oficial da AWS nem afiliado a ela.

---

## 1. Isso te afeta?

Você criou (ou vai criar) uma conta AWS? Então isso te afeta de um jeito
ou de outro — a resposta certa depende só de uma data:

- Conta criada **a partir de 15/07/2025** → você está no modelo novo, de
  créditos (seção 3). É o caso da maioria de quem está lendo isso agora.
- Conta criada **antes de 15/07/2025** → você está no modelo antigo, de 12
  meses grátis por serviço (seção 2), e nada do que mudou em 2025 afeta
  sua conta.

Se você não sabe em qual data sua conta foi criada, veja no **AWS Billing
and Cost Management console** — a informação do seu plano (Free ou Paid)
aparece lá.

## 2. Se sua conta é antiga (antes de 15/07/2025)

Você continua no modelo antigo: **12 meses grátis**, com limites fixos por
serviço, contados a partir da data em que você criou a conta. Exemplos:

- 5 GB de armazenamento S3 Standard
- 750 horas/mês de instância EC2 t2.micro ou t3.micro

Passar do limite não corta seu acesso nem fecha sua conta — você
simplesmente passa a pagar a tarifa normal pelo excedente. O limite grátis
não acumula: o que você não usar em um mês não passa para o mês seguinte.

Nada disso mudou com o anúncio de julho de 2025 — essa mudança afeta só
contas novas.

## 3. Se sua conta é nova (a partir de 15/07/2025): o modelo de créditos

Aqui o modelo é diferente:

- Você recebe **US$100 de crédito** ao criar a conta.
- Pode ganhar **até US$100 a mais** completando atividades de onboarding
  da AWS — total possível de **US$200**.
- Esse crédito vale por **6 meses**, ou até acabar, **o que vier primeiro**.
- Enquanto estiver no plano **Free**, você não é cobrado — só usa o
  crédito.

Até aqui, isso é o que a maioria do conteúdo em português sobre o assunto
já cobre. A parte que falta é a seção 5.

## 4. O que continua grátis nos dois casos: os serviços "Always Free"

Independente de qual modelo você está, mais de **30 serviços da AWS** têm
uma camada sempre gratuita, com limite mensal próprio, disponível tanto no
plano Free quanto no Paid — e ela continua valendo mesmo depois que seu
crédito de 6 meses ou seus 12 meses acabarem. Vale a pena olhar a lista
atual em [aws.amazon.com/free](https://aws.amazon.com/free) antes de
assumir que "acabou o grátis" significa "não tenho mais nada grátis".

## 5. O ponto que a AWS não deixa claro sozinho: o que acontece quando o plano Free acaba

Esta é a diferença real entre o modelo antigo e o novo, e é onde a própria
documentação da AWS se contradiz dependendo de qual página você lê.

Uma página oficial da AWS (a mais genérica e fácil de achar numa busca,
sobre "evitar cobranças inesperadas") diz, essencialmente, que depois que
sua elegibilidade ao free tier expira, "você passa a ser cobrado pela
tarifa padrão de uso" — o que soa como o comportamento do modelo antigo:
você continua com acesso, só passa a pagar.

Só que essa não é a informação relevante se você está no **plano Free**
(contas a partir de 15/07/2025). Outra página oficial, mais específica —
a que compara diretamente o plano Free com o plano Paid — diz claramente:

> "Depois que seu plano Free expira, sua conta fecha automaticamente, e
> você perde acesso aos seus recursos e dados."

Ou seja: no plano Free, quando os 6 meses (ou o crédito) acabam, **não é
que você passa a pagar** — sua conta **fecha sozinha**, e você perde
acesso ao que estava rodando. A AWS não conecta essas duas páginas para
deixar isso óbvio; se você só ler a mais genérica (a que aparece primeiro
em muitas buscas), pode achar, erradamente, que está seguro só porque vai
"passar a pagar" — quando na verdade sua conta vai fechar antes disso
acontecer.

**O que de fato acontece, em ordem:**

1. Seus 6 meses terminam, ou seu crédito acaba — o que vier primeiro.
2. A conta do plano Free **fecha automaticamente**.
3. Recursos param de rodar; você perde acesso a eles e aos seus dados.
4. A AWS **retém seu conteúdo por 90 dias** antes de excluir tudo
   permanentemente.
5. Dentro desses 90 dias, você pode **fazer upgrade para o plano Paid**
   para recuperar o acesso — qualquer crédito que sobrou é aplicado
   automaticamente na fatura seguinte.
6. Depois dos 90 dias, é definitivo: conta e recursos são excluídos para
   sempre.

## 6. Checklist prático antes do prazo acabar

- **Acompanhe o saldo de crédito e a data-limite** direto no console AWS
  Billing and Cost Management — não confie só em memória de quando você
  criou a conta.
- A AWS manda avisos automáticos por e-mail quando o crédito chega a
  **50%, 25% e 10%** restantes, e também **15, 7 e 2 dias** antes do
  prazo de 6 meses. Vale prestar atenção neles, mas não depender só
  deles — confirme direto no console de tempos em tempos.
- Decida com antecedência: você vai querer fazer **upgrade para o plano
  Paid** (mantém tudo, passa a pagar uso normal) ou prefere **desligar/
  exportar** o que for importante antes do fechamento automático?
- Se decidir não continuar, **desligue ou apague recursos que não
  precisa** antes do prazo, para não depender da janela de 90 dias como
  plano principal.

## 7. Onde conferir a informação oficial e atualizada

Este guia organiza o que está espalhado — não substitui a fonte oficial,
que pode mudar sem aviso:

- [aws.amazon.com/free](https://aws.amazon.com/free) — estrutura atual do
  plano Free/Paid e serviços Always Free.
- [aws.amazon.com/free/legacy/free-tier-faqs](https://aws.amazon.com/free/legacy/free-tier-faqs)
  — regras do modelo antigo (contas anteriores a 15/07/2025).
- Documentação de billing da AWS (`docs.aws.amazon.com`, seção "Choosing a
  plan" e "Avoiding unexpected charges") — comparação Free vs. Paid e
  comportamento de fechamento de conta.

---

*Guia preparado com base em fontes oficiais da AWS (aws.amazon.com/free,
aws.amazon.com/free/legacy/free-tier-faqs, e a documentação de billing da
AWS em docs.aws.amazon.com), verificadas em 10/08/2026. A AWS pode mudar
esses termos sem aviso — confirme informações críticas na fonte oficial
antes de agir. Este guia não é conteúdo oficial da AWS, não é afiliado a
ela, e não substitui os alertas e o console oficiais de billing.*

---

## Quer um checklist baixável, ou um aviso se a AWS mudar essas regras de novo?

Deixe seu e-mail. Não vira lista de outra coisa, e você pode sair quando
quiser.

> [ campo de e-mail ]
>
> [ ] Aceito receber e-mails sobre este assunto (checklist e avisos de
> mudança nas regras do AWS Free Tier). Você pode cancelar a qualquer
> momento pelo link no rodapé de qualquer e-mail, ou pedindo exclusão dos
> seus dados em [e-mail de contato a definir].
>
> [ Quero receber ]

*Aviso de privacidade: seu e-mail é usado só para o que está descrito
acima — nada de venda ou compartilhamento com terceiros para outros fins.
Cadastro e descadastro são geridos pela Brevo (plano gratuito), que já
cuida de opt-in duplo e cancelamento automaticamente. Para pedir a
exclusão dos seus dados a qualquer momento, escreva para [e-mail de
contato — a definir pelo dono do projeto].*

<!--
Implementação pendente: criar a conta Brevo (ação do dono do projeto —
fora do que este agente executa) e definir o e-mail de contato público
para pedidos de exclusão, antes de publicar. Checkbox de consentimento
não pode vir pré-marcado (LGPD, base legal = consentimento explícito).
-->
