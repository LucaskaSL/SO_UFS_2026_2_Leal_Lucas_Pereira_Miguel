# Atividade 1 de Sistemas Operacionais

Análise experimental de processos, threads e chamadas de sistema na execução local do modelo Mistral via Ollama, em execução com Open WebUI e scripts em Python. Projeto da disciplina de Sistemas Operacionais (UFS 2026.2).

- **Equipe:** Daniel Farani, Lucas Emanuel, Lucas Santana, Miguel Pereira, Paulo Medeiros.
- **Modelo:** Mistral-7B-Instruct-v0.3 (GGUF, Quantização Q4)
- **Camada de Aplicação:** Ollama + Open WebUI

## 1. Pré-requisitos e Ambiente

Os testes deste repositório foram homologados para ambientes Linux Nativo e WSL2/Ubuntu. Constatáva-se instalado:

* **Ollama** (v0.33.3)
* **Docker** (v29.8.0, build 88096ef)
* **Docker Compose** (v2.40.3-desktop.1)
* **Python** (v3.14.7)
* **Ferramentas de SO:** `strace`, `htop`

## 2. Instalação

### Passo 1: Instalar o motor de inferência (Ollama)
Execute o script oficial de instalação do Ollama no seu terminal:

``curl -fsSL [https://ollama.com/install.sh](https://ollama.com/install.sh) | sh``

### Passo 2: Baixar o modelo Mistral 7B
Com o Ollama instalado, realize o pull do modelo com quantização Q4 (aproximadamente 4.1GB):

``ollama pull mistral``

### Passo 3: Baixar Docker
A instalação do docker e da sua engine para rodar o container, foi realizada via download do Docker Desktop, encontrado em:

<https://docs.docker.com/desktop/>

### Passo 4: Baixar Python e bibliotecas externas
Para o Python:

``sudo apt update && sudo apt install python3 python3-pip`` 

ou alternativamente:

``sudo dnf install python3 python3-pip`` 

Agora para as bibliotecas externas:

``pip install requests matplotlib`` 

### Passo 5: Conferir se está tudo instalado corretamente
Para um comando geral, rode:

``ollama --version && ollama show mistral && docker --version && docker compose version && python --version && pip show requests matplotlib``

Alternativamente, você pode rodar comando por comando ao invés de um único.

## 3. Open WebUI
O serviço foi rodado via docker-compose, sendo necessário algumas configurações para que o Open WebUI pudesse conversar com o Mistral pelo Ollama:

``sudo systemctl edit ollama.service``

O que abre um painel, onde ficará tal configuração:

<img width="1366" height="646" alt="Captura de tela de 2026-09-12 14-12-31" src="https://github.com/user-attachments/assets/23dd1371-7985-4b84-89b1-11d5f5729725" />
Após isso rode:

``sudo systemctl daemon-reload``

``sudo systemctl restart ollama``

Sendo possível agora colocar na URL: ``http://localhost:3000``

Já na página do chat do Open WebUI, vá em "Configurações", então vá para "Conexões", e configure dessa forma:
<img width="1157" height="584" alt="Captura de tela de 2026-09-12 14-17-24" src="https://github.com/user-attachments/assets/b4c677a6-7387-4d02-8dc0-8732658fabf2" />

Agora a LLM do Mistral rodará, com uma demora de cerca de 6 minutos para resposta (registrado em testes pessoais)

## 4. Execução e Reprodução

Há três formas possíveis de executar o projeto, cada uma com um nível diferente de abstração e isolamento no Sistema Operacional

### 4.1 Rodando localmente
Esta é a forma mais direta e crua de interagir com o modelo, enviando caracteres de entrada e saída (I/O) diretamente pelo terminal do host, sem intermediários de rede complexos. Basta rodar:

``ollama run mistral``

Esse comando inicia uma sessão interativa no próprio terminal. O processo cliente do Ollama se comunica diretamente com o daemon ``llama-server`` operando em background, imprimindo os tokens na tela via streaming de texto. Ideal para verificar rapidamente se o modelo foi alocado corretamente na memória RAM.

### 4.2 Rodando o Open WebUI
Para subir a interface gráfica isolada em contêiner, inicialize o ambiente Docker com:

``docker compose up -d``

Em seguide, siga para a URL:

<http://localhost:3000>

O Docker cria um ambiente de rede isolado. A interface do WebUI roda dentro do contêiner e atua como um cliente HTTP. O Docker atua como a ponte de rede, roteando as requisições que saem da porta 8080 interna do contêiner para a porta 11434 do seu host, onde o motor do Ollama está escutando. Esta camada demonstra na prática o isolamento de processos e o roteamento de portas gerenciados pelo Kernel.

### 4.3 Testando os scripts em Python
Para os testes científicos e extração de métricas de hardware, sem a interferência e o peso visual de uma interface web, utilize o script de carga, estando na pasta scripts:

``python3 teste.py``

O script ignora completamente a interface Docker/WebUI e realiza requisições HTTP POST diretamente para a API REST do Ollama ``http://localhost:11434/api/generate``. O script força o motor a calcular toda a matriz da IA em silêncio e devolver um pacote JSON com a precisão em nanosegundos. É através desta execução que se torna possível medir o impacto exato do escalonamento de threads e monitorar as chamadas de sistema (syscalls) usando o ``strace``.

## 5. Configuração Estática de Hardware (Modelfile)

Além de forçar limites de hardware dinamicamente via script (passando parâmetros no JSON da requisição), o Ollama permite a criação de um Modelfile. Essa abordagem atua de forma análoga a um Dockerfile, criando uma imagem "congelada" do modelo já com as restrições de Sistema Operacional embutidas.

Isso garante rigor científico nos testes de bancada, pois o modelo forçará o Kernel Linux a respeitar os limites impostos, independentemente de quem faça a chamada (Terminal, Script ou WebUI).

Para mudar tal configuração, basta criar um arquivo chamado Modelfile (sem extensão mesmo) e fazer as configurações necessárias (como no exemplo encontrado no repositório). Após isso, basta "compilar" esse novo modelo no seu ambiente local, execute:

``ollama create mistral-4cores -f Modelfile``

Esse **mistral-4cores** é um nome qualquer que você pode dar a esse "novo" modelo. A partir desse momento, você pode realizar a inferência no modelo customizado usando o terminal ``ollama run mistral-4cores`` ou alterar o parâmetro ``"model": "mistral-4cores"`` no script ``teste.py``, garantindo o isolamento de recursos durante o monitoramento de processos.

## 6. Vídeo da atividade:
<https://youtu.be/2vLqXIa08Dk>
