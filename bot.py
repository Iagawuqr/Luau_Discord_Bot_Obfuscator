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
    with open(stats_file, "r") as f:
        data = json.load(f)
    return data

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

token = os.environ['DISCORD_TOKEN']

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
    if message.content.startswith("!obfuscate") and message.attachments:
        await process_obfuscation(message.author.id, str(message.author), message.attachments, message_to_delete=message, channel_to_fail=message.channel)
    await bot.process_commands(message)

@bot.tree.command(name="obfuscate", description="Ofusca um arquivo Lua")
@app_commands.describe(arquivo="O arquivo .lua ou .txt para ofuscar")
async def obfuscate_slash(interaction: discord.Interaction, arquivo: discord.Attachment):
    await interaction.response.send_message("Processando seu arquivo...", ephemeral=True)
    await process_obfuscation(interaction.user.id, str(interaction.user), [arquivo], channel_to_fail=interaction.channel)

bot.run(token)
