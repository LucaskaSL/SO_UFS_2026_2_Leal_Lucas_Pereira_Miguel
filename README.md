# SO_UFS_2026_2_Leal_Lucas_Pereira_Miguel

# OPEN WEBUI
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
