from typing import Type, cast

from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Message as OB11Message
from nonebot.adapters.onebot.v11.utils import unescape
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText
from nonebot.typing import T_State
from nonebot_plugin_saa import PlatformTarget

from ..apis import check_sub_target
from ..config import config
from ..config.db_config import SubscribeDupException
from ..platform import Platform, platform_manager
from ..types import Target
from .utils import common_platform, ensure_user_info, gen_handle_cancel


def do_add_sub(add_sub: Type[Matcher]):
    handle_cancel = gen_handle_cancel(add_sub, "已中止订阅")

    add_sub.handle()(ensure_user_info(add_sub))

    @add_sub.handle()
    async def init_promote(state: T_State):
        state["_prompt"] = (
            "请输入想要订阅的平台，目前支持，请输入冒号左边的名称：\n"
            + "".join(
                [
                    "{}：{}\n".format(
                        platform_name, platform_manager[platform_name].name
                    )
                    for platform_name in common_platform
                ]
            )
            + "要查看全部平台请输入：“全部”\n中止订阅过程请输入：“取消”"
        )

    @add_sub.got("platform", OB11Message.template("{_prompt}"), [handle_cancel])
    async def parse_platform(state: T_State, platform: str = ArgPlainText()) -> None:
        if not isinstance(state["platform"], Message):
            return
        if platform == "全部":
            message = "全部平台\n" + "\n".join(
                [
                    "{}：{}".format(platform_name, platform.name)
                    for platform_name, platform in platform_manager.items()
                ]
            )
            await add_sub.reject(message)
        elif platform == "取消":
            await add_sub.finish("已中止订阅")
        elif platform in platform_manager:
            state["platform"] = platform
        else:
            await add_sub.reject("平台输入错误")

    @add_sub.handle()
    async def prepare_get_id(matcher: Matcher, state: T_State):
        cur_platform = platform_manager[state["platform"]]
        if cur_platform.has_target:
            state["_prompt"] = (
                ("1." + cur_platform.parse_target_promot + "\n2.")
                if cur_platform.parse_target_promot
                else ""
            ) + "请输入订阅用户的id\n查询id获取方法请回复:“查询”"
        else:
            matcher.set_arg("raw_id", OB11Message("no id"))
            state["id"] = "default"
            state["name"] = await check_sub_target(state["platform"], Target(""))

    @add_sub.got("raw_id", OB11Message.template("{_prompt}"), [handle_cancel])
    async def got_id(state: T_State, raw_id: str = ArgPlainText()):
        if state.get("id"):
            return
        try:
            if raw_id == "查询":
                url = "https://nonebot-bison.netlify.app/usage/#%E6%89%80%E6%94%AF%E6%8C%81%E5%B9%B3%E5%8F%B0%E7%9A%84-uid"
                title = "Bison所支持的平台UID"
                content = "查询相关平台的uid格式或获取方式"
                image = "https://s3.bmp.ovh/imgs/2022/03/ab3cc45d83bd3dd3.jpg"
                getId_share = f"[CQ:share,url={url},title={title},content={content},image={image}]"  # 缩短字符串格式长度，以及方便后续修改为消息段格式
                await add_sub.reject(OB11Message(getId_share))
            platform = platform_manager[state["platform"]]
            raw_id = await platform.parse_target(unescape(raw_id))
            name = await check_sub_target(state["platform"], raw_id)
            if not name:
                await add_sub.reject("id输入错误")
            state["id"] = raw_id
            state["name"] = name
        except (Platform.ParseTargetException):
            await add_sub.reject("不能从你的输入中提取出id，请检查你输入的内容是否符合预期")
        else:
            await add_sub.send(
                "即将订阅的用户为:{} {} {}\n如有错误请输入“取消”重新订阅".format(
                    state["platform"], state["name"], state["id"]
                )
            )

    @add_sub.handle()
    async def prepare_get_categories(matcher: Matcher, state: T_State):
        if not platform_manager[state["platform"]].categories:
            matcher.set_arg("raw_cats", OB11Message(""))
            state["cats"] = []
            return
        state["_prompt"] = "请输入要订阅的类别，以空格分隔，支持的类别有：{}".format(
            " ".join(list(platform_manager[state["platform"]].categories.values()))
        )

    @add_sub.got("raw_cats", OB11Message.template("{_prompt}"), [handle_cancel])
    async def parser_cats(state: T_State, raw_cats: str = ArgPlainText()):
        if "cats" in state.keys():
            return
        res = []
        if platform_manager[state["platform"]].categories:
            for cat in raw_cats.split():
                if cat not in platform_manager[state["platform"]].reverse_category:
                    await add_sub.reject("不支持 {}".format(cat))
                res.append(platform_manager[state["platform"]].reverse_category[cat])
        state["cats"] = res

    @add_sub.handle()
    async def prepare_get_tags(matcher: Matcher, state: T_State):
        if not platform_manager[state["platform"]].enable_tag:
            matcher.set_arg("raw_tags", OB11Message(""))
            state["tags"] = []
            return
        state["_prompt"] = '请输入要订阅/屏蔽的标签(不含#号)\n多个标签请使用空格隔开\n订阅所有标签输入"全部标签"\n具体规则回复"详情"'

    @add_sub.got("raw_tags", OB11Message.template("{_prompt}"), [handle_cancel])
    async def parser_tags(state: T_State, raw_tags: str = ArgPlainText()):
        if "tags" in state.keys():
            return
        if raw_tags == "详情":
            await add_sub.reject(
                "订阅标签直接输入标签内容\n屏蔽标签请在标签名称前添加~号\n详见https://nonebot-bison.netlify.app/usage/#%E5%B9%B3%E5%8F%B0%E8%AE%A2%E9%98%85%E6%A0%87%E7%AD%BE-tag"
            )
        if raw_tags in ["全部标签", "全部", "全标签"]:
            state["tags"] = []
        else:
            state["tags"] = raw_tags.split()

    @add_sub.handle()
    async def add_sub_process(state: T_State):
        user = cast(PlatformTarget, state.get("target_user_info"))
        assert isinstance(user, PlatformTarget)
        try:
            await config.add_subscribe(
                user=user,
                target=state["id"],
                target_name=state["name"],
                platform_name=state["platform"],
                cats=state.get("cats", []),
                tags=state.get("tags", []),
            )
        except SubscribeDupException:
            await add_sub.finish(f"添加 {state['name']} 失败: 已存在该订阅")
        except Exception as e:
            await add_sub.finish(f"添加 {state['name']} 失败: {e}")
        await add_sub.finish("添加 {} 成功".format(state["name"]))