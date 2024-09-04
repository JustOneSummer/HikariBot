import asyncio
import base64
import functools
import hashlib
import os
from asyncio import Future
from concurrent.futures import ProcessPoolExecutor

import requests
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, NoticeEvent, Message
from requests.auth import HTTPBasicAuth

driver = get_driver()
minimap_renderer_temp = "minimap_renderer_temp"
executor = ProcessPoolExecutor(max_workers=10)


async def get_rep(wows_rep_file_base64: str, bot: Bot, ev: NoticeEvent):
    if wows_rep_file_base64.__contains__(".wowsreplay"):
        wowsrepla_file = wows_rep_file_base64
    else:
        file_hex = hashlib.sha256(wows_rep_file_base64.encode('utf-8')).hexdigest()
        file_bytes = base64.b64decode(wows_rep_file_base64)
        file_path_temp = os.getcwd() + os.sep + minimap_renderer_temp + os.sep + file_hex
        f_d = os.getcwd() + os.sep + minimap_renderer_temp
        if not os.path.exists(f_d):
            os.makedirs(f_d)
        wowsrepla_file = file_path_temp + ".wowsreplay"
        with open(wowsrepla_file, 'wb') as f:
            f.write(file_bytes)
            f.close()
    if not os.path.exists(wowsrepla_file):
        await bot.send(ev, MessageSegment.text("文件不存在，ll和nc 部署的请检查服务是否在一个服务器上，否则请开启base64功能"))
    else:
        await bot.send(ev, MessageSegment.text("正在处理replays文件.预计耗时1分钟"))
        group_id = int(ev.group_id)
        fr = executor.submit(functools.partial(upload_http, wowsrepla_file=wowsrepla_file))
        fr.add_done_callback(lambda future: send_video_call(bot=bot, group_id=group_id, future=future))


def upload_http(wowsrepla_file: str) -> str:
    upload_url = driver.config.minimap_renderer_url + "/upload_replays_video_url"
    with open(wowsrepla_file, 'rb') as file:
        files = {'file': file}
        response = requests.post(upload_url, files=files, auth=HTTPBasicAuth(driver.config.minimap_renderer_user_name, driver.config.minimap_renderer_password), timeout=600)
        if response.status_code == 200:
            return response.text
    return ""


def send_video_call(bot: Bot, group_id: int, future: Future):
    url = future.result()
    if url == "":
        asyncio.run(bot.send_group_msg(group_id=group_id, message=Message(MessageSegment.text("生成视频文件异常！请检查 minimap_renderer 是否要更新."))))
    else:
        # 构造视频文件消息
        data = str(driver.config.minimap_renderer_url + "/video_url?file_name=" + url.replace("\"", ""))
        asyncio.run(bot.send_group_msg(group_id=group_id, message=Message(MessageSegment.video(data))))


def get_file(url: str):
    response = requests.get(url)
    # 确保请求成功
    if response.status_code == 200:
        # 获取文件内容
        file_content = response.content

        # 对文件内容进行 Base64 编码
        encoded_content = base64.b64encode(file_content)

        # 将编码后的内容转换为字符串
        return encoded_content.decode('utf-8')
