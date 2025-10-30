import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import math
import os
import statistics

# Keep-alive server for Render
app = Flask('')
@app.route('/')
def home():
    return "I'm alive!"
def run():
    app.run(host='0.0.0.0', port=8080)
Thread(target=run).start()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "！"], intents=intents)

# 原初之星加權參數
weights = {"level": 100, "equip": 18, "skill": 7, "pet": 8, "relic": 33}
multipliers = {"level": 1, "equip": 5, "skill": 8, "pet": 4, "relic": 20}
season_max = {"level": 130, "equip": 650, "skill": 1040, "pet": 520, "relic": 260}
zh_names = {"level": "等級", "equip": "裝備", "skill": "技能", "pet": "寵物", "relic": "遺物"}

reward_thresholds = [
    (630, "副本加倍"), (680, "經驗加成"), (740, "昇華機率"), (800, "寶石加成"),
    (860, "副本加倍"), (920, "經驗加成"), (990, "昇華機率"), (1060, "寶石加成"),
    (1130, "副本加倍"), (1200, "經驗加成"), (1280, "昇華機率"), (1360, "寶石加成"),
    (1440, "加倍機率"), (1520, "經驗加成"), (1600, "最終獎勵")
]

def calculate_score(parts, current_score):
    try:
        keys = ["level", "equip", "skill", "pet", "relic"]
        raw = {k: float(parts[i]) for i, k in enumerate(keys)}
        adjusted = {k: raw[k] * multipliers[k] for k in keys}
        excess = {k: max(0, adjusted[k] - season_max[k]) for k in keys}
        weighted = {k: excess[k] * weights[k] for k in keys}
        total = sum(weighted.values())
        final_score = math.floor(total / 27 + 45)
        total_score = final_score + current_score
        return {"raw": raw, "final_score": final_score, "total_score": total_score}, None
    except Exception as e:
        return None, f"⚠️ 計算錯誤：{str(e)}"

def get_reward_status(score):
    for threshold, label in reversed(reward_thresholds):
        if score >= threshold:
            return f"🎁 達成獎勵：{label}（門檻 {threshold}）"
    next_target = next((t for t in reward_thresholds if score < t[0]), None)
    if next_target:
        return f"⛔ 尚未達成獎勵，距離下一階「{next_target[1]}」還差 {next_target[0] - score} 分"
    return "⛔ 尚未達成任何獎勵"

@bot.slash_command(name="原初", description="計算原初之星分數與獎勵")
async def primal(ctx, input: str):
    await process_input(ctx, input, recommend=False)

@bot.slash_command(name="原初推薦", description="推薦提升策略以達成下一階獎勵")
async def primal_recommend(ctx, input: str):
    await process_input(ctx, input, recommend=True)

@bot.slash_command(name="原初獎勵", description="列出所有原初之星獎勵門檻與獎項")
async def primal_rewards(ctx, score: int = 0):
    embed = discord.Embed(
        title="🎁 原初之星獎勵一覽表",
        description=f"目前分數：{score}，以下為各階段門檻與獎勵",
        color=0xF39C12
    )
    lines = []
    for threshold, label in reward_thresholds:
        if score >= threshold:
            lines.append(f"✅ {threshold}：{label}")
        else:
            lines.append(f"- {threshold}：{label}")
    embed.add_field(name="📊 獎勵階梯", value="\n".join(lines), inline=False)
    embed.set_footer(text="由原初之星計算器提供 ✨")
    await ctx.respond(embed=embed)

def safe_eval(expr):
    import re
    expr = re.sub(r'[^0-9\+\*\.\s]', '', expr)
    try:
        return eval(expr)
    except:
        return None

async def process_input(ctx, input: str, recommend: bool):
    await ctx.defer()
    try:
        parts = input.split('/')
        if len(parts) == 6 and '+' in parts[0]:
            current_score = int(parts[0].replace('+', ''))
            values = parts[1:]
        elif len(parts) == 5:
            current_score = 0
            values = parts
        else:
            await ctx.respond("⚠️ 輸入格式錯誤，請使用 `目前分數+/等級/裝備/技能/寵物/遺物` 或 `等級/裝備/技能/寵物/遺物`")
            return

        parsed_values = []
        for val in values:
            v = safe_eval(val)
            if v is None:
                await ctx.respond(f"⚠️ 無法解析欄位：`{val}`，請確認格式正確（可使用加法與乘法）")
                return
            parsed_values.append(v)

        result, error = calculate_score([str(v) for v in parsed_values], current_score)
        if error:
            await ctx.respond(error)
            return

        lines = [f"🌟 總原初之星：{result['total_score']}", get_reward_status(result["total_score"])]
        if recommend:
            lines.append("\n" + recommend_upgrades(result["final_score"], result["raw"]))
        else:
            future_rewards = [t for t in reward_thresholds if result["final_score"] < t[0]]
            if future_rewards:
                lines.append("\n📌 下一階段獎勵預告：")
                for i, (threshold, label) in enumerate(future_rewards[:2], 1):
                    lines.append(f"- 第 {i} 階：{label}（門檻 {threshold}）")

        await ctx.respond("\n".join(lines))
    except Exception as e:
        await ctx.respond(f"⚠️ 發生錯誤：{str(e)}")

@bot.slash_command(name="今日造型", description="看看今天各幫的副本運勢")
async def today_style(ctx):
    import random
    from datetime import datetime

    username = ctx.user.name
    today = datetime.now().strftime("%Y%m%d")
    seed = f"{username}-{today}"
    rng = random.Random(seed)

    styles = ["蒙眼幫", "眼鏡幫", "鐮刀幫", "不入幫"]
    style_emojis = {
        "蒙眼幫": "🫣", "眼鏡幫": "👓", "鐮刀幫": "🪓", "不入幫": "🙈"
    }

    result_lines = []
    for style in styles:
        double_count = red_gold_count = ascend_gold_count = 0
        for _ in range(4):
            if rng.random() < 0.25: double_count += 1
            if rng.random() < 0.02: red_gold_count += 1
            if rng.random() < 0.05: ascend_gold_count += 1
        line = f"{style_emojis[style]} {style}｜加倍：{double_count}｜紅金：{red_gold_count}｜昇華：{ascend_gold_count}"
        result_lines.append(line)

    embed = discord.Embed(
        title="🎭 今日造型報告",
        description=(
            f"👤 使用者：{username}\n📅 {today[:4]}/{today[4:6]}/{today[6:]}\n\n"
            "📘 看看今天各幫的副本運勢：\n"
            "🫣 蒙眼幫｜👓 眼鏡幫｜🪓 鐮刀幫｜🙈 不入幫\n"
            "每個幫派各自執行 4 次副本運勢判定，包含：\n"
            "✅ 加倍效果｜✨ 紅金裝｜🌟 昇華金裝\n\n"
            "同一使用者在同一天結果固定，不同使用者或日期則重新計算。"
        ),
        color=0x8E44AD
    )
    embed.add_field(name="📊 四幫派副本運勢", value="\n".join(result_lines), inline=False)
    embed.set_footer(text="原初之星造型系統 ✨")
    await ctx.respond(embed=embed)

@bot.slash_command(name="隨機", description="從多個選項中隨機選出一個")
async def random_choice(ctx, *options: str):
    import random
    if not options:
        await ctx.respond("⚠️ 請提供至少一個選項")
        return
    result = random.choice(options)
    await ctx.respond(f"🎲 隨機結果：{result}")

@bot.slash_command(name="隨機多選", description="從多個選項中隨機選出多個")
async def random_multi(ctx, count: int, *options: str):
    import random
    if count <= 0:
        await ctx.respond("⚠️ 選擇數量必須大於 0")
        return
    if count > len(options):
        await ctx.respond(f"⚠️ 選項不足，目前僅提供 {len(options)} 項")
        return
    results = random.sample(options, count)
    lines = [f"🎯 隨機選出 {count} 項："] + [f"- {r}" for r in results]
    await ctx.respond("\n".join(lines))

@bot.slash_command(name="help", description="顯示使用說明")
async def help_cmd(ctx):
    await ctx.respond(embed=get_help_embed())

@bot.slash_command(name="說明", description="顯示使用說明（中文別名）")
async def help_zh(ctx):
    await ctx.respond(embed=get_help_embed())

def get_help_embed():
    embed = discord.Embed(
        title="📘 原初之星計算器使用說明",
        description="快速計算原初之星分數，推薦最划算的提升策略，也支援造型運勢與隨機選擇功能",
        color=0x4A90E2
    )
    embed.add_field(
        name="📥 原初之星輸入格式",
        value=(
            "支援以下兩種格式：\n"
            "1️⃣ `目前分數+/等級/裝備/技能/寵物/遺物`（共 6 欄）\n"
            "2️⃣ `等級/裝備/技能/寵物/遺物`（共 5 欄，預設目前分數為 0）\n\n"
            "每欄皆可使用加法與乘法運算式，例如：\n"
            "`192/179*2+180*3/170*2+171*6/170/18`"
        ),
        inline=False
    )
    embed.add_field(
        name="📌 指令列表",
        value=(
            "`/原初`：計算原初之星分數與獎勵狀態\n"
            "`/原初推薦`：推薦三種提升策略（裝備主導、遺物主導、綜合平均）\n"
            "`/原初獎勵`：列出所有原初之星獎勵門檻與獎項（可輸入目前分數）\n"
            "`/今日造型`：看看今天各幫的副本運勢，幫助決定造型歸屬\n"
            "`/隨機`：從多個選項中隨機選出一個\n"
            "`/隨機多選`：從多個選項中隨機選出多個（可指定數量）\n"
            "`/help` 或 `/說明`：顯示本說明"
        ),
        inline=False
    )
    embed.set_footer(text="由原初之星計算器提供 ✨")
    return embed

# 啟動 Bot
bot.run(os.getenv("DISCORD_TOKEN"))
