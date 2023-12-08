from email.mime.text import MIMEText
from threading import Timer
import logging
import smtplib
import time
import paho.mqtt.client as mqtt
from informacoes import MQTT_BROKER_ADDRESS, MQTT_BROKER_PORT, MQTT_BROKER_USERNAME, MQTT_BROKER_PASSWORD, MQTT_TOPIC, email_from, email_password, email_to, email_subject, email_message, email_message2, email_message3

# Constantes de Temporizacao
CHECK_INTERVAL = 10

# Configuracoes dos Gateways
GATEWAYS = [
    {"topic": "ac1f09fffe06fcc6", "timeout": 86400, "nickname": "UNIJUI-GW / ID: ac1f09fffe06fcc6."},
    {"topic": "ac1f09fffe06fcd6", "timeout": 86400, "nickname": "Hospital_VS-GW	/ ID: ac1f09fffe06fcd6."},
    {"topic": "ac1f09fffe06fcd4", "timeout": 86400, "nickname": "Vila_Sete-GW / ID: ac1f09fffe06fcd4."},
    {"topic": "ac1f09fffe06fcd7", "timeout": 86400, "nickname": "Prefeitura-GW / ID: ac1f09fffe06fcd7."},
    {"topic": "ac1f09fffe06fcd9", "timeout": 86400, "nickname": "Edificio_Puntel-GW / ID: ac1f09fffe06fcd9."},
    {"topic": "ac1f09fffe06fccb", "timeout": 86400, "nickname": "Roberto-GW / ID: ac1f09fffe06fccb."},
    {"topic": "ac1f09fffe06fcda", "timeout": 86400, "nickname": "Bela_Uniao-GW / ID: ac1f09fffe06fcda."},
    {"topic": "ac1f09fffe06fcc2", "timeout": 86400, "nickname": "Candeia_Baixa-GW / ID: ac1f09fffe06fcc2."},
    {"topic": "ac1f09fffe06fcd2", "timeout": 86400, "nickname": "Rincao_dos_Rolin-GW / ID: ac1f09fffe06fcd2."},
    {"topic": "ac1f09fffe06fcc7", "timeout": 86400, "nickname": "Horizontina-GW / ID: ac1f09fffe06fcc7."},
    {"topic": "7276ff000b031fce", "timeout": 86400, "nickname": "Sede / ID: 7276ff000b031fce."},
    {"topic": "7276ff000b032aa0", "timeout": 86400, "nickname": "Campus / ID: 7276ff000b032aa0."},
    {"topic": "7276ff000b031f41", "timeout": 86400, "nickname": "Irder / ID: 7276ff000b031f41."}
]

# Dicionário para armazenar os temporizadores de cada gateway
GATEWAY_TIMERS = {}

# Dicionário para armazenar os tempos das últimas mensagens recebidas por gateway
LAST_MESSAGE_TIMES = {gateway["topic"]: {"last_time": time.time(), "original_timeout": gateway["timeout"], "email_sent": False} for gateway in GATEWAYS}

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuracao de Email
EMAIL_SMTP_SERVER = 'smtp.gmail.com'
EMAIL_SMTP_PORT = 587

# Funcao para enviar o email
def send_email(apelido, timeout_original_hrs):
    msg = MIMEText(email_message + apelido + email_message2 + str(timeout_original_hrs) + email_message3)
    msg['Subject'] = email_subject
    msg['From'] = email_from
    msg['To'] = email_to

    try:
        server = smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT)
        server.starttls()
        server.login(email_from, email_password)
        server.sendmail(email_from, email_to, msg.as_string())
        server.quit()
        logger.info("Email enviado com sucesso.")
    except Exception as e:
        logger.error("Erro ao enviar email: %s", str(e))

# Funcao para lidar com a recepcao de mensagens MQTT
def on_message(client, userdata, msg):
    # Decodifica a mensagem recebida para Latin-1
    payload = msg.payload.decode('latin-1')

    # Verifica se algum trecho da mensagem corresponde a algum dos IDs dos gateways
    for gateway in GATEWAYS:
        if payload.find(gateway["topic"]) != -1:
            # Reinicia o temporizador
            if gateway["topic"] in GATEWAY_TIMERS:
                GATEWAY_TIMERS[gateway["topic"]].cancel()  # Cancela o temporizador anterior, se existir

                # Define o indicador email_sent como False ao reiniciar o temporizador
                LAST_MESSAGE_TIMES[gateway["topic"]]["email_sent"] = False

            # Verifica se o e-mail foi enviado anteriormente
            if LAST_MESSAGE_TIMES[gateway["topic"]]["email_sent"]:
                # Se o e-mail foi enviado anteriormente, reinicia o temporizador sem enviar outro e-mail
                timer = Timer(gateway["timeout"], send_email_on_timer, args=(gateway["topic"],))
            else:
                # Se o e-mail não foi enviado anteriormente, inicia o temporizador normalmente
                timer = Timer(gateway["timeout"], send_email, args=(gateway["apelido"], gateway["timeout"]/3600))

            GATEWAY_TIMERS[gateway["topic"]] = timer
            timer.start()

            gateway_info = LAST_MESSAGE_TIMES[gateway["topic"]]
            gateway_info["last_time"] = time.time()
            
            # Calcula o timeout original em horas
            timeout_original_hrs = gateway_info["original_timeout"] / 3600

            # Não envia o email aqui; enviará quando o temporizador atingir o tempo limite

    logger.info("Mensagem recebida: %s", payload)
# Funcao para enviar email quando o temporizador atingir o tempo limite
def send_email_on_timer(topic):
    try:
        gateway_info = LAST_MESSAGE_TIMES[topic]
        timeout_original_hrs = gateway_info["original_timeout"] / 3600
    
        # Verifica se o e-mail já foi enviado
        if not gateway_info["email_sent"]:
            # Envia o email com o apelido do gateway e o timeout original convertido para horas
            send_email(GATEWAYS[0]["apelido"], timeout_original_hrs)

            # Atualiza o indicador de e-mail enviado
            gateway_info["email_sent"] = True
    except Exception as e:
        logger.error("Erro ao executar a função send_email_on_timer: %s", str(e))

# Funcao para reconectar
def reconnect():
    try:
        logger.info("Tentando reconectar...")
        client.reconnect()
    except Exception as e:
        logger.error("Erro durante a reconexão: %s", str(e))
        logger.info("Tentando reconectar em 10 segundos...")
        time.sleep(10)
        reconnect()

# Conecta ao Broker MQTT e subscreve aos tópicos dos gateways
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Conectado ao Broker com código de resultado: %s", str(rc))
        # Assina todos os tópicos ao se conectar
        client.subscribe(MQTT_TOPIC)
    else:
        logger.error("Falha na conexão com o Broker. Código de resultado: %s", str(rc))
        logger.info("Tentando reconectar em 10 segundos...")
        time.sleep(10)
        reconnect()

# Configura o cliente MQTT
client = mqtt.Client()
client.username_pw_set(MQTT_BROKER_USERNAME, MQTT_BROKER_PASSWORD)

# Configura as funcoes de callback
client.on_message = on_message
client.on_connect = on_connect

# Conecta-se ao Broker MQTT
client.connect(MQTT_BROKER_ADDRESS, MQTT_BROKER_PORT, 60)

# Inicializa os temporizadores para cada gateway
for gateway in GATEWAYS:
    timer = Timer(gateway["timeout"], send_email_on_timer, args=(gateway["topic"],))
    GATEWAY_TIMERS[gateway["topic"]] = timer
    timer.start()

# Inicia o loop do cliente MQTT
client.loop_start()

try:
    # Mantém o script em execução enquanto aguarda a interrupção
    while True:
        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    logger.info("Encerrando o programa...")
    # Para o loop do cliente MQTT
    client.loop_stop()
    # Espera que as threads do temporizador concluam
    time.sleep(5)
    logger.info("Programa encerrado.")
