import discord
from discord.ext import commands, tasks
import requests
import os
import subprocess
import shutil
import keep_alive
from itertools import cycle

import json
import asyncio
from discord import app_commands

# Initialize or load stats
stats_file = "stats.json"
if not os.path.exists(stats_file):
    with open(stats_file, "w") as f:
        json.dump({"total_obfuscations": 0, "users": {}}, f)

def increment_stats(user_id, original_size, obfuscated_size):
    user_id = str(user_id)
    with open(stats_file, "r") as f:
        data = json.load(f)
    
    data["total_obfuscations"] += 1
    
    if "users" not in data:
        data["users"] = {}
        
    if user_id not in data["users"]:
        data["users"][user_id] = {"count": 0, "total_original_size": 0, "total_obfuscated_size": 0}
    
    user_data = data["users"][user_id]
    user_data["count"] += 1
    user_data["total_original_size"] += original_size
    user_data["total_obfuscated_size"] += obfuscated_size
    user_data["last_ob"] = {
        "original_size": original_size,
        "obfuscated_size": obfuscated_size
    }
    
    with open(stats_file, "w") as f:
        json.dump(data, f)

def get_stats():
    if not os.path.exists(stats_file):
        return {"total_obfuscations": 0, "users": {}}
    with open(stats_file, "r") as f:
        try:
            data = json.load(f)
        except:
            return {"total_obfuscations": 0, "users": {}}
    
    # Ensure keys exist
    if "total_obfuscations" not in data: data["total_obfuscations"] = 0
    if "users" not in data: data["users"] = {}
    return data

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

token = os.environ['DISCORD_TOKEN']

def obfuscation(path, author):
    copy = f".//obfuscated//{author}.lua"

    if os.path.exists(copy):
        os.remove(copy)

    shutil.copyfile(path, copy)

    text_file = open(f".//obfuscate.lua", "r")
    data = text_file.read()
    text_file.close()
    f = open(copy, "a")
    f.truncate(0)
    f.write(data)
    f.close()

    originalupload = open(path, "r")
    originalupload_data = originalupload.read()
    originalupload.close()

    with open(copy, "r") as in_file:
        buf = in_file.readlines()

    with open(copy, "w") as out_file:
        for line in buf:
            if line == "--SCRIPT\n":
                line = line + originalupload_data + '\n'
            out_file.write(line)

    output = subprocess.getoutput(f'bin/luvit {copy}')

    if os.path.exists(f".//obfuscated//{author}-obfuscated.lua"):
        os.remove(f".//obfuscated//{author}-obfuscated.lua")

    f = open(f".//obfuscated//{author}-obfuscated.lua", "a")
    f.write(output)
    f.close()

    os.remove(copy)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        keep_alive.keep_alive()

bot = MyBot()
bot.remove_command("help")

# Helper for pagination
class PaginationView(discord.ui.View):
    def __init__(self, pages, user):
        super().__init__(timeout=60)
        self.pages = pages
        self.user = user
        self.current_page = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    @discord.ui.button(label="←", style=discord.ButtonStyle.gray)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.pages[self.current_page])

    @discord.ui.button(label="→", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.pages[self.current_page])

def create_totalob_embed(user_id):
    data = get_stats()
    total = data["total_obfuscations"]
    embed = discord.Embed(title="Estatísticas Globais", color=discord.Color.blue())
    embed.add_field(name="Total de Ofuscações", value=str(total), inline=False)
    
    uid_str = str(user_id)
    if uid_str in data["users"]:
        user_data = data["users"][uid_str]
        last = user_data.get("last_ob", {"original_size": 0, "obfuscated_size": 0})
        embed.add_field(name="Sua última ofuscação", value=f"Original: {last['original_size']} bytes\nOfuscado: {last['obfuscated_size']} bytes", inline=False)
        embed.add_field(name="Seu total", value=f"{user_data['count']} scripts", inline=True)
    return embed

@bot.command(name="totalob")
async def totalob_cmd(ctx):
    await ctx.send(embed=create_totalob_embed(ctx.author.id))

@bot.tree.command(name="totalob", description="Mostra o total de ofuscações")
async def totalob_slash(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_totalob_embed(interaction.user.id))

def create_userobs_pages(user):
    data = get_stats()
    users = data.get("users", {})
    if not users:
        return [discord.Embed(description="Nenhum dado de usuário ainda.")]

    sorted_users = sorted(users.items(), key=lambda x: x[1]['count'], reverse=True)
    pages = []
    items_per_page = 5
    for i in range(0, len(sorted_users), items_per_page):
        embed = discord.Embed(title="Top Ofuscadores", color=discord.Color.gold())
        chunk = sorted_users[i:i + items_per_page]
        for idx, (uid, udata) in enumerate(chunk):
            embed.add_field(name=f"{i + idx + 1}. Usuário {uid}", value=f"Scripts: {udata['count']}\nOriginal Total: {udata['total_original_size']} bytes\nOfuscado Total: {udata['total_obfuscated_size']} bytes", inline=False)
        pages.append(embed)
    return pages

@bot.command(name="userobs")
async def userobs_cmd(ctx):
    pages = create_userobs_pages(ctx.author)
    if len(pages) == 1:
        await ctx.send(embed=pages[0])
    else:
        await ctx.send(embed=pages[0], view=PaginationView(pages, ctx.author))

@bot.tree.command(name="userobs", description="Mostra o ranking de ofuscadores")
async def userobs_slash(interaction: discord.Interaction):
    pages = create_userobs_pages(interaction.user)
    if len(pages) == 1:
        await interaction.response.send_message(embed=pages[0])
    else:
        await interaction.response.send_message(embed=pages[0], view=PaginationView(pages, interaction.user))

async def process_obfuscation(author_id, author_name, attachments, message_to_delete=None, channel_to_fail=None):
    for attachment in attachments:
        url = attachment.url
        if '.txt' in url or '.lua' in url:
            uploads_dir = ".//uploads//"
            obfuscated_dir = ".//obfuscated//"
            if not os.path.exists(uploads_dir): os.makedirs(uploads_dir)
            if not os.path.exists(obfuscated_dir): os.makedirs(obfuscated_dir)

            response = requests.get(url)
            original_size = len(response.content)
            path = f".//uploads//{author_name}.lua"
            if os.path.exists(path): os.remove(path)
            with open(path, "wb") as f: f.write(response.content)
            
            obfuscation(path, author_name)
            ob_path = f".//obfuscated//{author_name}-obfuscated.lua"
            obfuscated_size = os.path.getsize(ob_path)
            increment_stats(author_id, original_size, obfuscated_size)

            user = await bot.fetch_user(author_id)
            try:
                await user.send(f"Aqui está seu código ofuscado!\nOriginal: {original_size} bytes\nOfuscado: {obfuscated_size} bytes", file=discord.File(ob_path))
            except discord.Forbidden:
                if channel_to_fail:
                    await channel_to_fail.send(f"<@{author_id}>, não consegui te enviar DM! Abra suas mensagens diretas.")
    
    if message_to_delete:
        try: await message_to_delete.delete()
        except: pass

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    # Process obfuscation if it starts with !obfuscate and has attachments
    if message.content.startswith("!obfuscate") and message.attachments:
        await process_obfuscation(message.author.id, str(message.author), message.attachments, message_to_delete=message, channel_to_fail=message.channel)
    
    # Also allow sending the file directly to DM without the command
    elif isinstance(message.channel, discord.DMChannel) and message.attachments:
        await process_obfuscation(message.author.id, str(message.author), message.attachments, channel_to_fail=message.channel)

    await bot.process_commands(message)

@bot.tree.command(name="obfuscate", description="Ofusca um arquivo Lua")
@app_commands.describe(arquivo="O arquivo .lua ou .txt para ofuscar")
async def obfuscate_slash(interaction: discord.Interaction, arquivo: discord.Attachment):
    await interaction.response.send_message("Processando seu arquivo...", ephemeral=True)
    await process_obfuscation(interaction.user.id, str(interaction.user), [arquivo], channel_to_fail=interaction.channel)

bot.run(token)
