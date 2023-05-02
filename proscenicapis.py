from time import sleep
import io
import aiohttp
import asyncio

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

import json
import hashlib

from PIL import Image, ImageDraw

from ._block import decompress as lz4_decompress
#import lz4.block
#lz4_decompress = lz4.block.decompress

US_HOST_PATH = 'mobile.proscenic.tw'
EU_HOST_PATH = 'mobile.proscenic.com.de'
CN_HOST_PATH = 'mobile.proscenic.cn'
ROOT_URL = 'https://' + US_HOST_PATH
VACUUM_TYPE = 'CleanRobot'

EOL = '#\t#'


class ProscenicHome:
    def __init__(self, username, password, token=None, host_path=US_HOST_PATH):
        self.username = username
        self.password = password
        self.token = token
        self.host_path = host_path
        self.url = 'https://' + self.host_path
        self.vacuums = []  # type: list[ProscenicHomeVacuum]

    async def connect(self):
        if not self.token:
            self.token = await self.get_token()
        devices = await self.get_devices()
        for device in devices:
            if 'typeName' in device:
                if device['typeName'] == VACUUM_TYPE:
                    vacuum = ProscenicHomeVacuum(self, device)
                    did_connect = await vacuum.connect()
                    if not did_connect:
                        self.token = await self.get_token()
                        did_connect = await vacuum.connect()
                        if not did_connect:
                            continue
                        self.vacuums.append(vacuum)
                        return
                    self.vacuums.append(vacuum)

    async def get_devices(self):
        url = self.url + '/user/getEquips/' + self.username
        data = {
            'username': self.username,
        }
        response = await self.send_post_command(url, data)
        return response['data']['content']

    async def get_token(self):
        url = self.url + '/user/login'

        headers = {
            'os': 'i',
            'Content-Type': 'application/json',
            'c': '338',
            'lan': 'en',
            'Host': self.host_path,
            'User-Agent': 'ProscenicHome/1.7.8 (iPhone; iOS 14.2.1; Scale/3.00)',
            'v': '1.7.8'
        }

        hashed_password = hashlib.md5(self.password.encode('utf-8')).hexdigest()
        data = json.dumps({
            "state": "欧洲",
            "countryCode": "49",
            "appVer": "1.7.8",
            "type": "2",
            "os": "IOS",
            "password": hashed_password,
            "registrationId": "13165ffa4eb156ac484",
            "language": "EN",
            "username": self.username,
            "pwd": self.password
        }).encode()

        response = await self.send_post_command(url, data, headers)
        self.token = response['data']['token']
        return response['data']['token']

    @staticmethod
    async def send_post_command(url, data, headers=None):
        try:
            async with aiohttp.ClientSession() as session:
                if headers:
                    async with session.post(url, headers=headers, data=data) as response:
                        response = await response.json()
                        return response
                else:
                    async with session.post(url, data=data) as response:
                        response = await response.json()
                        return response
        except:
            raise ValueError

    @staticmethod
    async def send_socket_message(message_string, socket_ip, socket_port, target_message_count=1):
        reader, writer = await asyncio.open_connection(socket_ip, socket_port)

        writer.write(message_string.encode())
        await writer.drain()
        json_data_list = []
        for i in range(target_message_count):
            try:
                read_async = reader.readuntil(b'#\t#')
                byte_data = await asyncio.wait_for(read_async, timeout=8)
                string = byte_data.decode('utf-8')
                string = string.split(EOL)[0]
                json_data_list.append(json.loads(string))
            except:
                break
        writer.close()
        return json_data_list

    @staticmethod
    def decrypt(encrypted_message, token):
        try:
            aes_key = token
            encrypted_message = encrypted_message

            decoder = base64.b64decode
            encrypted_bytes = decoder(encrypted_message)
            secret_key = aes_key.encode("utf-8")
            cipher = AES.new(secret_key, AES.MODE_ECB)

            decrypted = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
            return decrypted.decode('utf-8').rstrip('\0')
        except:
            raise ValueError


class ProscenicHomeVacuum:
    def __init__(self, proscenic_home, device):
        self.proscenic_home = proscenic_home
        self.device = device
        self.serial = device['sn']
        self.name = device['name']
        self.uid = device['sn']
        self.socket_ip = None
        self.socket_prot = None
        self.status = {'mode': 'charge'}
        self.map_data = None
        self.path_data = None

    async def connect(self):
        did_connect = await self.update_sockets_ip()
        return did_connect

    async def update_sockets_ip(self):
        sockets = await self.get_socket_address()
        if 'code' in sockets:
            if sockets['code'] == 102:
                return False
        self.socket_ip = sockets['data']['addr_list'][0]['ip']
        self.socket_prot = sockets['data']['addr_list'][0]['port']
        return True

    async def update_state(self):
        if not self.socket_ip:
            await self.update_sockets_ip()

        infoType70001 = json.dumps({
            "data":
                {
                    "token": self.proscenic_home.token,
                    "sn": self.serial
                },
            "infoType": 70001
        }) + EOL

        infoType70003 = json.dumps({
            "data":
                {
                    "token": self.proscenic_home.token,
                    "sn": self.serial
                },
            "infoType": 70003
        }) + EOL

        #await self.get_info()
        #await asyncio.sleep(2)

        json_data_list = await self.proscenic_home.send_socket_message(
            infoType70001,
            self.socket_ip,
            self.socket_prot,
            4
        )

        for json_data in json_data_list:
            if 'encrypt' in json_data:
                is_encrypted = json_data['encrypt']
                if is_encrypted == 1:
                    await self.process_encrypted_data(json_data['data'])

    async def process_encrypted_data(self, encrypted_data):
        try:
            decrypted_data = self.proscenic_home.decrypt(encrypted_data, self.proscenic_home.token)
        except ValueError:
            if not await self.connect():
                await self.proscenic_home.get_token()
                try:
                    decrypted_data = self.proscenic_home.decrypt(encrypted_data, self.proscenic_home.token)
                except ValueError:
                    return

        decrypted_json = json.loads(decrypted_data)
        info_type = decrypted_json['infoType']
        if info_type == 20001:
            self.update_status_20001(decrypted_json)
        elif info_type == 20002:
            self.update_map_20002(decrypted_json)
        elif info_type == 30000:
            self.update_path_data_30000(decrypted_json)

    def update_status_20001(self, status_data):
        self.status = status_data['data']

    def update_map_20002(self, map_data):
        self.map_data = map_data['data']

    def update_path_data_30000(self, path_data):
        self.path_data = path_data['data']

    def get_name(self):
        return self.name

    async def get_socket_address(self):
        url = self.proscenic_home.url + '/appInit/getSockAddr'
        headers = {
            'token': self.proscenic_home.token,
        }
        data = {
            'username': self.proscenic_home.username,
            'sn': self.serial
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def start_clean(self):
        url = self.proscenic_home.url + '/instructions/cmd21005/' + self.serial + '?username=' + self.proscenic_home.username
        headers = {
            'host': self.proscenic_home.host_path,
            'token': self.proscenic_home.token,
        }
        data = {
            'cleanMode': "sweepOnly",
            'mode': "smartAreaClean"
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def start_deep_clean(self):
        url = self.proscenic_home.url + '/instructions/cmd21005_2/' + self.serial + '?username=' + self.proscenic_home.username
        headers = {
            'host': self.proscenic_home.host_path,
            'token': self.proscenic_home.token,
        }
        data = {
            'mode': "depthTotalClean"
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def clean_segment(self, comma_seperated_string_of_segment_ids):
        url = self.proscenic_home.url + '/instructions/cmd21005/' + self.serial + '?username=' + self.proscenic_home.username
        headers = {
            'host': self.proscenic_home.host_path,
            'token': self.proscenic_home.token,
        }
        data = {
            'segmentId': comma_seperated_string_of_segment_ids
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def collect_dust(self):
        url = self.proscenic_home.url + '/instructions/cmd/' + self.serial + '?username=' + self.proscenic_home.username
        headers = {
            'host': self.proscenic_home.host_path,
            'token': self.proscenic_home.token,
        }
        data = {
            "dInfo": {
                "ts": "1675216377168",
                "userId": self.proscenic_home.username
            },
            "data": {
                "cmd": "startDustCenter",
                "value": 0
            },
            "infoType": 21024
        }
        data = json.dumps(data)

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def pause_cleaning(self):
        url = self.proscenic_home.url + '/instructions/' + self.serial + '/21017' + '?username=' + self.proscenic_home.username
        headers = {
            'host': self.proscenic_home.host_path,
            'token': self.proscenic_home.token,
        }
        data = {
            'mode': "pause"
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def continue_cleaning(self):
        url = self.proscenic_home.url + '/instructions/' + self.serial + '/21017' + '?username=' + self.proscenic_home.username
        headers = {
            'host': self.proscenic_home.host_path,
            'token': self.proscenic_home.token,
        }
        data = {
            'pauseOrContinue': "continue"
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def return_to_dock(self):
        url = self.proscenic_home.url + '/instructions/' + self.serial + '/21012' + '?username=' + self.proscenic_home.username
        headers = {
            'host': self.proscenic_home.host_path,
            'token': self.proscenic_home.token,
        }
        data = {
            'charge': "start"
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def proscenic_powermode(self, mode):
        url = self.proscenic_home.url + '/instructions/' + self.serial + '/21022' + '?username=' + self.proscenic_home.username
        headers = {
            'host': self.proscenic_home.host_path,
            'token': self.proscenic_home.token,
        }
        data = {
            'setMode': mode
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    async def get_info(self):
        url = self.proscenic_home.url + '/app/cleanRobot/info'
        headers = {
            'token': self.proscenic_home.token,
        }
        data = {
            'username': self.proscenic_home.username,
            'sn': self.serial
        }

        response = await self.proscenic_home.send_post_command(url, data, headers)
        return response

    def get_map(self):
        if not self.map_data:
            w, h = 429, 255
            shape = ((40, 40), (w - 10, h - 10))

            # creating new Image object
            image = Image.new("RGB", (w, h))

            # create rectangle image
            draw_image = ImageDraw.Draw(image)
            draw_image.rectangle(shape, fill="black")
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            return img_byte_arr

        return self.draw_map(
            self.map_data['map'],
            [self.map_data['width'], self.map_data['height']],
            self.status['pos'],
            self.map_data['x_min'],
            self.map_data['y_min'],
            self.map_data['resolution'])

    def draw_map(self, map_string, map_dimentions, robot_pos=None, x_min=0, y_min=0, resolution=0.05):
        clean_map_string = map_string.replace(" ", "+")
        decoder = base64.b64decode
        zipped_data = decoder(clean_map_string)
        decompressed = lz4_decompress(zipped_data, (map_dimentions[0] * map_dimentions[1]))

        x_min = x_min * 1000.0
        y_min = y_min * 1000.0
        resolution = resolution * 1000.0

        image = Image.frombytes("L", (map_dimentions[0], map_dimentions[1]), decompressed)
        image = image.convert('RGBA')

        pixels = image.load()
        for y in range(image.size[1]):
            for x in range(image.size[0]):
                if pixels[x, y] == (127, 127, 127, 255):
                    pixels[x, y] = (0, 0, 0, 0)
                elif pixels[x, y] == (0, 0, 0, 255):
                    pixels[x, y] = (15, 60, 152, 255)
                elif pixels[x, y] == (255, 255, 255, 255):
                    pixels[x, y] = (3, 98, 142, 255)
                elif pixels[x, y] == (1, 1, 1, 255):
                    pixels[x, y] = (5, 153, 99, 255)
                elif pixels[x, y] == (2, 2, 2, 255):
                    pixels[x, y] = (9, 153, 5, 255)
                elif pixels[x, y] == (3, 3, 3, 255):
                    pixels[x, y] = (141, 153, 5, 255)
                elif pixels[x, y] == (4, 4, 4, 255):
                    pixels[x, y] = (153, 103, 5, 255)
                elif pixels[x, y] == (5, 5, 5, 255):
                    pixels[x, y] = (153, 40, 5, 255)
                elif pixels[x, y] == (6, 6, 6, 255):
                    pixels[x, y] = (153, 5, 58, 255)
                elif pixels[x, y] == (7, 7, 7, 255):
                    pixels[x, y] = (151, 5, 153, 255)
                elif pixels[x, y] == (8, 8, 8, 255):
                    pixels[x, y] = (96, 5, 153, 255)
                elif pixels[x, y] == (9, 9, 9, 255):
                    pixels[x, y] = (40, 5, 153, 255)

        draw_image = ImageDraw.Draw(image)
        if robot_pos:
            robot_pos_x = round((robot_pos[0] - x_min) / resolution)
            robot_pos_y = round((robot_pos[1] - y_min) / resolution)
            draw_image.ellipse(
                (
                    (robot_pos_x - 3, robot_pos_y - 3),
                    (robot_pos_x + 3, robot_pos_y + 3)
                )
                ,
                fill="white"
            )

        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        return img_byte_arr