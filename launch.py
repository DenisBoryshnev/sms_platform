import toml
import argparse
import socket
import json
import base64
import logging

# Настройка логирования
logging.basicConfig(filename='sms_client.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')


def load_config():
    with open('config.toml', 'r') as file:
        config = toml.load(file)
    return config['sms_service']


def parse_arguments():
    parser = argparse.ArgumentParser(description="SMS Sender CLI")
    parser.add_argument('--sender', required=True, help="Номер отправителя")
    parser.add_argument('--recipient', required=True, help="Номер получателя")
    parser.add_argument('--message', required=True, help="Текст сообщения")
    return parser.parse_args()


class HTTPRequest:
    def __init__(self, method, url, headers, body):
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body

    def to_bytes(self):
        headers_str = "\r\n".join([f"{k}: {v}" for k, v in self.headers.items()])
        request_line = f"{self.method} {self.url} HTTP/1.1"
        return f"{request_line}\r\n{headers_str}\r\n\r\n{self.body}".encode()


class HTTPResponse:
    def __init__(self, status_code, headers, body):
        self.status_code = status_code
        self.headers = headers
        self.body = body

    @classmethod
    def from_bytes(cls, binary_data):
        data = binary_data.decode()
        headers, body = data.split("\r\n\r\n", 1)
        status_line, *header_lines = headers.split("\r\n")
        status_code = int(status_line.split(" ")[1])
        headers_dict = dict(line.split(": ", 1) for line in header_lines)
        return cls(status_code, headers_dict, body)


def send_http_request(config, sender, recipient, message):
    try:
        url = "/send_sms"
        body = json.dumps({
            "sender": sender,
            "recipient": recipient,
            "message": message
        })
        headers = {
            "Host": config['server_address'],
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "Authorization": "Basic " + base64.b64encode(
                f"{config['username']}:{config['password']}".encode()
            ).decode()
        }

        request = HTTPRequest("POST", url, headers, body)

        server_address, server_port = config['server_address'].split(":")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((server_address, int(server_port)))
            s.sendall(request.to_bytes())

            response_data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response_data += chunk

        response = HTTPResponse.from_bytes(response_data)
        return response

    except socket.error as e:
        logging.error(f"Ошибка подключения к серверу: {e}")
        return HTTPResponse(500, {}, json.dumps({"error": "Connection error"}))
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        return HTTPResponse(500, {}, json.dumps({"error": "Internal error"}))


def main():
    config = load_config()
    args = parse_arguments()
    logging.info(f"Отправка SMS: отправитель={args.sender}, получатель={args.recipient}, сообщение={args.message}")
    response = send_http_request(config, args.sender, args.recipient, args.message)
    logging.info(f"Ответ сервера: код={response.status_code}, тело={response.body}")
    print(f"Код ответа: {response.status_code}")
    print(f"Тело ответа: {response.body}")


if __name__ == "__main__":
    main()