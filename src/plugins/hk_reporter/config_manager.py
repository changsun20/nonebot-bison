from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, Event, GroupMessageEvent
from nonebot.permission import Permission
from nonebot.adapters.cqhttp.permission import GROUP_ADMIN, GROUP_MEMBER, GROUP_OWNER
from nonebot import on_command

from .platform.utils import check_sub_target
from .config import Config, NoSuchSubscribeException

async def check_is_owner_or_admin(bot: Bot, event: Event):
    return await (GROUP_ADMIN | GROUP_OWNER)(bot, event)

# add_sub = on_command("添加订阅", rule=to_me(), permission=Permission(check_is_owner_or_admin), priority=5)
add_sub = on_command("添加订阅", rule=to_me(), priority=5)
# add_sub = on_command("添加订阅", rule=to_me() & check_is_owner_or_admin, priority=5)
@add_sub.handle()
async def _(bot: Bot, event: Event, state: T_State):
    args = str(event.get_message()).strip().split()
    if len(args) != 2:
        await add_sub.reject("使用方法为： 添加订阅 平台 id")
        return
    target_type, target = args
    if (name := await check_sub_target(target_type, target)):
        config: Config = Config()
        config.add_subscribe(event.group_id, "group", target, name, target_type)
        await add_sub.finish("成功添加 {}".format(name))
    else:
        await add_sub.reject("平台或者id不存在")
    
query_sub = on_command("查询订阅", rule=to_me(), priority=5)
@query_sub.handle()
async def _(bot: Bot, event: Event, state: T_State):
    config: Config = Config()
    sub_list = config.list_subscribe(event.group_id, "group")
    res = '订阅的帐号为：\n'
    for sub in sub_list:
        res += '{} {} {}\n'.format(sub['target_type'], sub['target_name'], sub['target'])
    await query_sub.finish(res)

del_sub = on_command("删除订阅", rule=to_me(), priority=5)
@del_sub.handle()
async def _(bot: Bot, event: Event, state: T_State):
    args = str(event.get_message()).strip().split()
    if len(args) != 2:
        await del_sub.reject("使用方法为： 删除订阅 平台 id")
        return
    target_type, target = args
    config = Config()
    try:
        config.del_subscribe(event.group_id, "group", target, target_type)
    except NoSuchSubscribeException:
        await del_sub.reject('平台或id不存在')
    await del_sub.finish('删除成功')
