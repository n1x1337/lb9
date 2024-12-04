import tornado.ioloop
import tornado.web
import tornado.websocket
import redis
import uuid
import logging
import tornado.gen

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

redis_client = redis.StrictRedis(host='localhost', port=6379, decode_responses=True)

clients = {}


class ChatWebSocketHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        self.client_id = str(uuid.uuid4())
        clients[self] = self.client_id
        logging.info(f"Новое подключение: {self.client_id}")

        self.write_message(f"Вы вошли в чат с ID: {self.client_id}")
        self.send_online_clients()

    def on_message(self, message):
        logging.info(f"Сообщение от клиента ({self.client_id}): {message}")
        redis_client.publish('chat_channel', f"{self.client_id}: {message}")

    def on_close(self):
        client_id = clients.pop(self, None)
        if client_id:
            logging.info(f"Подключение закрыто: {client_id}")
            self.send_online_clients()

    def send_online_clients(self):
        online_clients = [f"id: {client_id}" for client_id in clients.values()]
        online_clients_message = {"type": "online_clients", "clients": online_clients}
        for client in clients.keys():
            client.write_message(online_clients_message)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


async def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('chat_channel')
    logging.info("Подписка на канал Redis: chat_channel")

    while True:
        message = pubsub.get_message()
        if message and message['type'] == 'message':
            logging.info(f"Сообщение из Redis: {message['data']}")
            for client in clients.keys():
                client.write_message({"type": "message", "data": message["data"]})
        await tornado.gen.sleep(0.1)


def make_app():
    return tornado.web.Application([
        (r"/websocket", ChatWebSocketHandler),
        (r"/", MainHandler),
    ], template_path=".")


if __name__ == "__main__":
    app = make_app()
    app.listen(8888)
    logging.info("Сервер запущен на http://localhost:8888")

    tornado.ioloop.IOLoop.current().spawn_callback(redis_listener)
    tornado.ioloop.IOLoop.current().start()
