import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import math
import os

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

# 原初之星參數
multipliers = {"level": 1, "equip": 5, "skill": 8, "pet": 4, "relic": 20}
weights = {"level": 100, "equip": 18, "skill": 7, "pet": 8, "relic": 33}
season_max = {
    "level": 130,
    "equip": 130 * 5,
    "skill": 130 * 8,
    "pet": 130 * 4,
    "relic": 13 * 20
}
reward_thresholds = [
    (680, "經驗加成"),
    (740, "昇華機率"),
    (800, "寶石加成"),
    (860, "加倍機率"),
    (920, "經驗加成")
]
zh_names = {
    "level": "等級",
    "equip": "裝備",
    "skill": "技能",
    "pet": "寵物",
    "relic": "遺物"
}

def evaluate_value(value_str, multiplier):
    value_str = value_str.replace(' ', '')
    try:
        return float(value_str) * multiplier
    except ValueError:
        try:
            terms = value_str.split('*')
            product = 1
            for term in terms:
                sum_parts = map(float, term.split('+'))
                product *= sum(sum_parts)
            return product
        except:
            return None

def calculate_score(parts, current_score):
    keys = ["level", "equip", "skill", "pet", "relic"]
    raw, adj, weighted = {}, {}, {}
    for i, key in enumerate(keys):
        val = evaluate_value(parts[i], multipliers[key])
        if val is None:
            return None, f"⚠️ `{zh_names[key]}` 欄位格式錯誤：{parts[i]}"
        raw[key] = val
        adj[key] = max(0, val - season_max[key])
        weighted[key] = adj[key] * weights[key]
    total_weighted = sum(weighted.values())
    final_score = math.floor(total_weighted / 27 + 45)
    total_score = final_score + current_score
    return {
        "raw": raw,
        "adj": adj,
        "weighted": weighted,
        "total_weighted": total_weighted,
        "final_score": final_score,
        "total_score": total_score
    }, None

def get_reward_status(score):
    for threshold, label in reversed(reward_thresholds):
        if score >= threshold:
            return f"🎁 達成獎勵：{label}（門檻 {threshold}）"
    next_reward = next((t for t in reward_thresholds if score < t[0]), None)
    if next_reward:
        diff = next_reward[0] - score
        return f"⛔ 尚未達成獎勵，距離下一階「{next_reward[1]}」還差 {diff} 分"
    return "⛔ 尚未達成任何獎勵"

def recommend_upgrades(score, raw):
    next_targets = [t for t in reward_thresholds if score < t[0]]
    if not next_targets:
        return "🎉 已達成所有獎勵！"

    next_score = next_targets[0][0]
    second_score = next_targets[1][0] if len(next_targets) > 1 else None
    keys = ["level", "equip", "skill", "pet", "relic"]
    best = []

    for key in keys:
        for delta in range(1, 11):
            test_raw = raw.copy()
            test_raw[key] += delta
            test_parts = [str(test_raw[k]) for k in keys]
            result, _ = calculate_score(test_parts, 0)
            if result and result["final_score"] >= next_score:
                best.append((key, delta, result["final_score"]))
                break

    best.sort(key=lambda x: x[1])
    lines = [f"🔍 推薦提升組合（達成 {next_score}）："]
    for key, delta, new_score in best:
        label = next(t[1] for t in reward_thresholds if new_score >= t[0])
        lines.append(f"- {zh_names[key]} +{delta} → 分數 {new_score} ✅ {label}")

    if second_score:
        lines.append(f"\n🔮 進階推薦（達成 {second_score}）：")
        for key in keys:
            test_raw = raw.copy()
            test_raw[key] += 5
            test_parts = [str(test_raw[k]) for k in keys]
            result, _ = calculate_score(test_parts, 0)
            if result and result["final_score"] >= second_score:
                label = next(t[1] for t in reward_thresholds if result["final_score"] >= t[0])
                lines.append(f"- {zh_names[key]} +5 → 分數 {result['final_score']} ✅ {label}")
    return "\n".join(lines)

async def process_input(ctx, input_str, recommend):
    parts = input_str.strip().split('/')
    if '+' in parts[0]:
        try:
            current_score = int(eval(parts[0].replace('+', '')))
        except:
            await ctx.respond("❗ 無法解析上季末總原初表達式")
            return
        parts = parts[1:]
    else:
        current_score = 0
        if len(parts) == 6:
            parts = parts[1:]

    if len(parts) != 5:
        await ctx.respond("❗ 請輸入格式為 [上季末總原初+]/等級/裝備/技能/寵物/遺物")
        return

    result, error = calculate_score(parts, current_score)
    if error:
        await ctx.respond(error)
        return

    total_score = result["total_score"]
    lines = [
        f"🌟 總原初之星：{total_score}",
        get_reward_status(total_score)
    ]

    if recommend:
        lines.append("\n" + recommend_upgrades(total_score, result["raw"]))

    await ctx.respond("\n".join(lines))

@bot.slash_command(name="s2", description="計算原初之星分數")
async def s2(ctx, input: str):
    await process_input(ctx, input, recommend=False)

@bot.slash_command(name="S2", description="計算原初之星分數並推薦提升")
async def S2(ctx, input: str):
    await process_input(ctx, input, recommend=True)
    
@bot.slash_command(name="help", description="顯示使用說明")
async def help(ctx):
    embed = discord.Embed(
        title="📘 原初之星計算器使用說明",
        description="使用指令快速計算你的原初之星分數，並查看是否達成獎勵門檻。",
        color=0x00bfff
    )
    embed.add_field(
        name="📌 指令格式",
        value=(
            "/s2 等級/裝備/技能/寵物/遺物\n"
            "/s2 上季末總原初+/等級/裝備/技能/寵物/遺物\n"
            "/S2（大寫）會額外顯示推薦提升組合\n"
            "*可輸入平均等級或各等級加總\n"
            "*如 169.6 或 170*3+169*2"
        ),
        inline=False
    )
    embed.add_field(
        name="📎 範例",
        value="/s2 /192/175/170/170/18\n/S2 650+/192/175/170/170/18",
        inline=False
    )
    embed.add_field(
        name="📊 回應內容",
        value=(
            "🌟 總原初之星：計算後的分數\n"
            "🎁 獎勵狀態：是否達成（如 經驗加成、昇華機率）\n"
            "🔍 推薦提升組合：僅 `/S2` 指令顯示"
        ),
        inline=False
    )
    embed.set_footer(text="如有格式錯誤，Bot 會提示你修正。")
    await ctx.respond(embed=embed)

# 文字指令支援
@bot.command()
async def s2(ctx, *, input: str):
    await process_input(ctx, input, recommend=False)

@bot.command()
async def S2(ctx, *, input: str):
    await process_input(ctx, input, recommend=True)

@bot.command(name="help")
async def help_command(ctx):
    await help(ctx)

# 啟動 Bot
bot.run(os.getenv("DISCORD_TOKEN"))
