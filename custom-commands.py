import discord
from discord.ext import commands, flags
import asyncpg
import databaseutils
import typing
import asyncio
import datetime
import re
import random

converters = [converter().convert for name, converter in vars(commands).items() if name.endswith("Converter")][1:-1].append(int)


class Embed(discord.Embed):
    def __init__(self, bot, message: typing.Union[commands.Context, discord.Message] = None, **kwargs):
        super().__init__(**kwargs)
        asyncio.create_task(self.__ainit__(bot, message, **kwargs))

    async def __ainit__(self, bot, message, **kwargs):
        if isinstance(message, commands.Context):
            message = message.message
        title = kwargs.get("title")
        if title:
            kwargs.pop("title")

        if message and message.guild:
            row = await bot.db.get("guild_colours", ["colour"], {"guildid": message.guild.id})
        else:
            row = None

        colour = row[0][0] if row else 0x000000
        kwargs["colour"] = kwargs.get("colour", colour)

        if title:
            avatar_url = message.author.avatar_url_as(format="png") if message else None
            self.set_author(name=title, icon_url=avatar_url)

        icon_url = bot.user.avatar_url_as(format="png")

        if message:
            self.set_footer(text=message.clean_content, icon_url=icon_url)
        else:
            self.set_footer(icon_url=icon_url)

        self.timestamp = datetime.datetime.utcnow()


class Bot(commands.Bot):
    session = databaseutils.DatabaseHandler(user="postgres", database="custom-commands", host="localhost", password="angelo2005")
    cache = {}
    regex = r"\{\{([^{}]+)\}\}"
    group_regex = r"\$([1-9][0-9]*)"
    allowed_attrs = {
        r"{{content}}": lambda ctx, match: ctx.message.content,
        r"{{author_mention}}": lambda ctx, match: ctx.author.mention,
        r"{{author_name}}": lambda ctx, match: ctx.author.name,
        r"{{author_descriminator}}": lambda ctx, match: ctx.author.descriminator,
        r"{{owner_mention}}": lambda ctx, match: f"<@{ctx.guild.owner_id}>",
        r"{{owner_name}}": lambda ctx, match: ctx.guild.get_member(ctx.guild.owner_id).name,
        r"{{owner_descriminator}}": lambda ctx, match: ctx.guild.get_member(ctx.guild.owner_id).descriminator,
    }
    special = {
        r"(rnd|random)\((([^,],)*[^,]+),?\)": lambda ctx, match: random.choice(match.groups(2).split(",")),
    }

    async def add_custom_command(self, guildid, name, returnstr, args):
        await self.session.insert("commands", [guildid, name, returnstr, args])
        if name not in self.cache:
            self.cache[name] = {}
        self.cache[name][guildid] = [returnstr, args]

    def flagcommand(self, *args, **kwargs):
        def inner(command):
            flag = flags.command(*args, **kwargs)(command)
            self.add_command(flag)
            return flag
        return inner

    async def convert_arg(self, ctx, arg):
        for converter in converters:
            try:
                return await converter(ctx, arg)
            except commands.CommandError:
                continue

    async def format_message(self, ctx, args, format):
        format = list(format)
        for match in re.finditer(self.regex, "".join(format)):
            start = match.start(0)
            end = match.end(0)
            group = match.group(1)
            arg = re.match(self.group_regex, group)
            if (arg):
                try:
                    format[start:end] = args[int(arg.group(1))-1]
                except IndexError:
                    pass
            i = 0
            while True:
                converted = False
                for k, v in self.special.items():
                    match = re.match(k, "".join(format)[start+2:end-2])
                    if (match):
                        format[start+2:end-2] = v(ctx, match)
                        converted = True
                if not converted and i:
                    break
                i += 1
            for match in re.finditer(self.regex, "".join(format)):
                print("".join(format)[match.start():match.end()])
                for k, v in self.allowed_attrs.items():
                    allowed_match = re.match(k, match.group(0))
                    if (allowed_match):
                        format[match.start():match.end()] = v(ctx, allowed_match)
            return "".join(format)


bot = Bot("!")
bot.load_extension("jishaku")


@bot.event
async def on_ready():
    rows = await bot.session.get("commands", [], {})
    for row in rows:
        if row[1] not in bot.cache:
            bot.cache[row[1]] = {}
        print(row)
        bot.cache[row[1]][row[0]] = [row[2], row[3]]
        @bot.command(name=row[1])
        @commands.check(lambda _ctx:  _ctx.guild.id in bot.cache[_ctx.command.name])
        async def _command(_ctx, *args):
            await _ctx.send(await bot.format_message(_ctx, args, bot.cache[_ctx.command.name][_ctx.guild.id][0]))
    print("Ready!")


@flags.add_flag("--return", nargs="*")
@flags.add_flag("--args", type=int, default=0)
@bot.flagcommand()
async def create(ctx, name, **options):
    options["return"] = " ".join(options["return"])
    rows = await bot.session.get("commands", [], {"guildid": ctx.guild.id, "name": name})
    if rows:
        return await ctx.send(Embed(bot, ctx, description="A command already exists with that name"))

    await bot.add_custom_command(ctx.guild.id, name, options["return"], options["args"])

    @bot.command(name=name)
    @commands.check(lambda _ctx:  _ctx.guild.id in bot.cache[_ctx.command.name])
    async def _command(_ctx, *args):
        await _ctx.send(await bot.format_message(_ctx, args, bot.cache[_ctx.command.name][_ctx.guild.id][0]))


bot.run("NTAwNDE0NTYwMDk3MDA5Njc1.Xla20w.8t7gG5_4i4r-bshPixaFOJkWD_I")
