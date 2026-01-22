import discord
from discord.ext import commands, tasks
import requests
import os
import subprocess
import shutil
import keep_alive
from itertools import cycle
from dotenv import load_dotenv
import json
from discord import app_commands
from datetime import datetime, timedelta

# Carregar variáveis do arquivo .env
load_dotenv()

# Initialize or load stats
stats_file = "stats.json"
OWNER_ID = int(os.getenv('OWNER_ID', 1372234679276670990))

# Garantir que o arquivo de stats tenha todas as chaves necessárias
def initialize_stats():
    if not os.path.exists(stats_file):
        data = {
            "total_obfuscations": 0, 
            "users": {},
            "config": {
                "enabled": True,
                "daily_limit": 5,
                "admins": [OWNER_ID]
            }
        }
        with open(stats_file, "w") as f:
            json.dump(data, f)
        return data
    return None

initialize_stats()

def get_stats():
    if not os.path.exists(stats_file):
        initialize_stats()
    
    with open(stats_file, "r") as f:
        try:
            data = json.load(f)
        except:
            data = {"total_obfuscations": 0, "users": {}, "config": {"enabled": True, "daily_limit": 5, "admins": [OWNER_ID]}}
    
    # Garantir que todas as chaves existam
    defaults = {
        "total_obfuscations": 0,
        "users": {},
        "config": {"enabled": True, "daily_limit": 5, "admins": [OWNER_ID]}
    }
    
    for key, default_value in defaults.items():
        if key not in data:
            data[key] = default_value
    
    if "admins" not in data["config"]:
        data["config"]["admins"] = [OWNER_ID]
    
    return data

def save_stats(data):
    with open(stats_file, "w") as f:
        json.dump(data, f, indent=2)

def increment_stats(user_id, original_size, obfuscated_size):
    user_id = str(user_id)
    data = get_stats()
    
    data["total_obfuscations"] += 1
    
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "count": 0, 
            "total_original_size": 0, 
            "total_obfuscated_size": 0, 
            "daily_count": 0, 
            "last_reset": datetime.now().isoformat(),
            "last_ob": {"original_size": 0, "obfuscated_size": 0}
        }
    
    user_data = data["users"][user_id]
    
    # Garantir que todas as chaves existam
    required_keys = ["daily_count", "last_reset", "last_ob", "count", 
                     "total_original_size", "total_obfuscated_size"]
    for key in required_keys:
        if key not in user_data:
            if key == "daily_count":
                user_data[key] = 0
            elif key == "last_reset":
                user_data[key] = datetime.now().isoformat()
            elif key == "last_ob":
                user_data[key] = {"original_size": 0, "obfuscated_size": 0}
            else:
                user_data[key] = 0
    
    # Verificar reset diário
    try:
        last_reset = datetime.fromisoformat(user_data["last_reset"])
    except:
        last_reset = datetime.now()
        user_data["last_reset"] = last_reset.isoformat()
    
    if datetime.now() - last_reset > timedelta(days=1):
        user_data["daily_count"] = 0
        user_data["last_reset"] = datetime.now().isoformat()
    
    user_data["count"] += 1
    user_data["daily_count"] += 1
    user_data["total_original_size"] += original_size
    user_data["total_obfuscated_size"] += obfuscated_size
    user_data["last_ob"] = {
        "original_size": original_size,
        "obfuscated_size": obfuscated_size
    }
    
    save_stats(data)

def is_admin(user_id):
    data = get_stats()
    return user_id in data["config"]["admins"] or user_id == OWNER_ID

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

# Pegar token do .env
token = os.getenv('DISCORD_TOKEN')
if not token:
    raise ValueError("DISCORD_TOKEN não encontrado no arquivo .env!")

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
        embed.add_field(name="Sua última ofuscação", 
                       value=f"Original: {last['original_size']} bytes\nOfuscado: {last['obfuscated_size']} bytes", 
                       inline=False)
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
            embed.add_field(name=f"{i + idx + 1}. Usuário {uid}", 
                          value=f"Scripts: {udata['count']}\nOriginal: {udata['total_original_size']} bytes\nOfuscado: {udata['total_obfuscated_size']} bytes", 
                          inline=False)
        pages.append(embed)
    return pages

@bot.command(name="userobs")
async def userobs_cmd(ctx):
    pages = create_userobs_pages(ctx.author)
    if len(pages) == 1:
        await ctx.send(embed=pages[0])
    else:
        await ctx.send(embed=pages[0], view=PaginationView(pages, ctx.author))

@bot.tree.command(name="config", description="Configurações do bot (Apenas Owner)")
@app_commands.describe(
    status="Ativar ou desativar ofuscação",
    limite="Limite diário por usuário"
)
async def config_slash(interaction: discord.Interaction, status: bool = None, limite: int = None):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Apenas o proprietário pode usar este comando!", ephemeral=True)
        return

    data = get_stats()
    if status is not None:
        data["config"]["enabled"] = status
    if limite is not None:
        data["config"]["daily_limit"] = limite
    
    save_stats(data)

    embed = discord.Embed(title="Configurações do Bot", color=discord.Color.blue())
    embed.add_field(name="Status da Ofuscação", 
                   value="✅ Ativado" if data["config"]["enabled"] else "❌ Desativado", 
                   inline=True)
    embed.add_field(name="Limite Diário", 
                   value=f"{data['config']['daily_limit']} scripts", 
                   inline=True)
    embed.add_field(name="Admins", 
                   value=f"{len(data['config']['admins'])} configurados", 
                   inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setadmin", description="Adiciona um administrador (Apenas Owner)")
async def setadmin_slash(interaction: discord.Interaction, usuario: discord.User):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Apenas o proprietário pode usar este comando!", ephemeral=True)
        return

    data = get_stats()
    if usuario.id not in data["config"]["admins"]:
        data["config"]["admins"].append(usuario.id)
        save_stats(data)
        await interaction.response.send_message(f"{usuario.mention} agora é um administrador!")
    else:
        await interaction.response.send_message(f"{usuario.mention} já é um administrador!")

@bot.tree.command(name="ping", description="Verifica a latência do bot")
async def ping_slash(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latência: {latency}ms")

@bot.command(name="ping")
async def ping_cmd(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latência: {latency}ms")

async def process_obfuscation(author_id, author_name, attachments, message_to_delete=None, channel_to_fail=None):
    data = get_stats()
    
    # Global check
    if not data["config"]["enabled"] and author_id != OWNER_ID:
        if channel_to_fail:
            await channel_to_fail.send(f"<@{author_id}>, a ofuscação está temporariamente desativada pelo administrador.")
        return

    # Rate limit check
    user_id_str = str(author_id)
    if user_id_str in data["users"] and author_id != OWNER_ID:
        udata = data["users"][user_id_str]
        last_reset = datetime.fromisoformat(udata.get("last_reset", datetime.now().isoformat()))
        if datetime.now() - last_reset > timedelta(days=1):
            udata["daily_count"] = 0
            udata["last_reset"] = datetime.now().isoformat()
            save_stats(data)
        
        if udata["daily_count"] >= data["config"]["daily_limit"]:
            next_reset = last_reset + timedelta(days=1)
            wait_time = next_reset - datetime.now()
            hours = int(wait_time.total_seconds() // 3600)
            minutes = int((wait_time.total_seconds() % 3600) // 60)
            if channel_to_fail:
                await channel_to_fail.send(f"<@{author_id}>, você atingiu seu limite diário ({data['config']['daily_limit']}). Tente novamente em {hours}h {minutes}m.")
            return

    for attachment in attachments:
        url = attachment.url
        if '.txt' in url or '.lua' in url:
            uploads_dir = ".//uploads//"
            obfuscated_dir = ".//obfuscated//"
            if not os.path.exists(uploads_dir): 
                os.makedirs(uploads_dir)
            if not os.path.exists(obfuscated_dir): 
                os.makedirs(obfuscated_dir)

            response = requests.get(url)
            original_size = len(response.content)
            path = f".//uploads//{author_name}.lua"
            
            if os.path.exists(path): 
                os.remove(path)
            
            with open(path, "wb") as f: 
                f.write(response.content)
            
            obfuscation(path, author_name)
            ob_path = f".//obfuscated//{author_name}-obfuscated.lua"
            obfuscated_size = os.path.getsize(ob_path)
            increment_stats(author_id, original_size, obfuscated_size)

            user = await bot.fetch_user(author_id)
            try:
                await user.send(
                    f"Aqui está seu código ofuscado!\n"
                    f"Original: {original_size} bytes\n"
                    f"Ofuscado: {obfuscated_size} bytes", 
                    file=discord.File(ob_path)
                )
            except discord.Forbidden:
                if channel_to_fail:
                    await channel_to_fail.send(f"<@{author_id}>, não consegui te enviar DM! Abra suas mensagens diretas.")
    
    if message_to_delete:
        try: 
            await message_to_delete.delete()
        except: 
            pass

@bot.event
async def on_message(message):
    if message.author.bot: 
        return
    
    # Process obfuscation if it starts with !obfuscate and has attachments
    if message.content.startswith("!obfuscate") and message.attachments:
        await process_obfuscation(
            message.author.id, 
            str(message.author), 
            message.attachments, 
            message_to_delete=message, 
            channel_to_fail=message.channel
        )
    
    # Also allow sending the file directly to DM without the command
    elif isinstance(message.channel, discord.DMChannel) and message.attachments:
        await process_obfuscation(
            message.author.id, 
            str(message.author), 
            message.attachments, 
            channel_to_fail=message.channel
        )

    await bot.process_commands(message)

@bot.tree.command(name="obfuscate", description="Ofusca um arquivo Lua")
@app_commands.describe(arquivo="O arquivo .lua ou .txt para ofuscar")
async def obfuscate_slash(interaction: discord.Interaction, arquivo: discord.Attachment):
    await interaction.response.send_message("Processando seu arquivo...", ephemeral=True)
    await process_obfuscation(
        interaction.user.id, 
        str(interaction.user), 
        [arquivo], 
        channel_to_fail=interaction.channel
    )

# Status cycling
status = cycle(['OBFUSCATED READY', 'Use /obfuscate', f'Owner: {OWNER_ID}'])

@tasks.loop(seconds=10)
async def change_status():
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=next(status)
        )
    )

@bot.event
async def on_ready():
    print(f'{bot.user} está online!')
    change_status.start()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=next(status)
        )
    )

bot.run(token)
