import asyncio
import base64
import hashlib
import os
import queue
import traceback
from concurrent.futures import ProcessPoolExecutor

import requests
from nonebot import get_driver, get_bots
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, NoticeEvent, Message
from nonebot.log import logger
from requests.auth import HTTPBasicAuth

driver = get_driver()
minimap_renderer_temp = "minimap_renderer_temp"
# 创建一个队列对象

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
        group_id = int(ev.group_id)
        bot_id = bot.self_id
        if driver.config.minimap_renderer_poll:
            qs = MinimapRendererQueueData.QUEUES.qsize()
            if qs <= 0:
                await bot.send(ev, MessageSegment.text(f"正在处理..."))
            else:
                await bot.send(ev, MessageSegment.text(f"正在处理... 当前队列任务数量：{qs}"))
            MinimapRendererQueueData.QUEUES.put(MinimapRendererQueueData(wowsrepla_file=wowsrepla_file, group_id=group_id))
        else:
            await bot.send(ev, MessageSegment.text("正在处理replays文件.预计耗时1分钟"))
            asyncio.get_event_loop().run_in_executor(None, replays_run, bot_id, group_id, wowsrepla_file)


# 消费队列
def consumer_queue(bot_id):
    if MinimapRendererQueueData.ON_STATUS == 1:
        return
    while True:
        try:
            item = MinimapRendererQueueData.QUEUES.get_nowait()
            if not item is None:
                replays_run(bot_id=bot_id, group_id=item.group_id, wowsrepla_file=item.wowsrepla_file)
        except queue.Empty:
            continue
        except Exception as e:
            print(f"minimap消费队列异常 {e}")


def replays_run(bot_id, group_id: int, wowsrepla_file: str):
    try:
        bot = get_bots().get(bot_id)
        if bot:
            url = upload_http(wowsrepla_file=wowsrepla_file)
            send_video(bot=bot, group_id=group_id, url=url)
        else:
            print(f"机器人{bot_id} 获取实例失败！")
            logger.error(bot_id + " 获取实例失败！")
    except (Exception):
        logger.error(traceback.format_exc())


def upload_http(wowsrepla_file: str) -> str:
    logger.info(f"上传replays... {wowsrepla_file}")
    upload_url = driver.config.minimap_renderer_url + "/upload_replays_video_url"
    with open(wowsrepla_file, 'rb') as file:
        files = {'file': file}
        response = requests.post(upload_url, files=files, auth=HTTPBasicAuth(driver.config.minimap_renderer_user_name, driver.config.minimap_renderer_password), timeout=600)
        if response.status_code == 200:
            return response.text
    return ""


def send_video(bot: Bot, group_id: int, url: str):
    if url == "":
        asyncio.run(bot.send_group_msg(group_id=group_id, message=Message(MessageSegment.text("生成视频文件异常！请检查 minimap_renderer 是否要更新."))))
    else:
        # 构造视频文件消息
        logger.info(f"发送replays视频... {url}")
        data = str(driver.config.minimap_renderer_url + "/video_url?file_name=" + url.replace("\"", ""))
        asyncio.run(bot.send_group_msg(group_id=group_id, message=Message(MessageSegment.video(data, timeout=600))))
        logger.info(f"成功发送replays视频... {url}")


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


class MinimapRendererQueueData:
    QUEUES = queue.Queue()
    ON_STATUS = 0

    def __init__(self, wowsrepla_file, group_id):
        """
        初始化 MinimapRendererQueueData 实例。

        :param wowsrepla_file: 用于渲染的小地图数据
        :param group_id: 与该数据关联的组ID
        """
        self.wowsrepla_file = wowsrepla_file
        self.group_id = group_id
