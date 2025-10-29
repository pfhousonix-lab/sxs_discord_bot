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

def recommend_upgrades(current_final_score, raw):
    next_targets = [t for t in reward_thresholds if current_final_score < t[0]]
    if not next_targets:
        return "🎉 已達成所有獎勵！"

    next_score = next_targets[0][0]
    keys = ["level", "equip", "skill", "pet", "relic"]
    value_table = {key: weights[key] * multipliers[key] for key in keys}

    from itertools import product

    combos = []
    for deltas in product(range(0, 11), repeat=5):
        test_raw = raw.copy()
        for i, key in enumerate(keys):
            test_raw[key] += deltas[i]
        test_parts = [str(test_raw[k]) for k in keys]
        result, _ = calculate_score(test_parts, 0)
        if result and result["final_score"] >= next_score:
            total_value = sum(deltas[i] * value_table[keys[i]] for i in range(5))
            combos.append((deltas, result["final_score"], total_value))

    if not combos:
        return f"⚠️ 無法在每欄最多 +10 的範圍內達成 {next_score} 分"

    combos.sort(key=lambda x: -x[2])
    top_combos = combos[:2]

    lines = [f"🔍 效益最大推薦（達成 {next_score} 分）："]
    for idx, (deltas, achieved_score, value) in enumerate(top_combos, 1):
        label = next(t[1] for t in reward_thresholds if achieved_score >= t[0])
        lines.append(f"\n📈 組合 {idx}（總效益 = {value:.1f}）：")
        for i, delta in enumerate(deltas):
            if delta > 0:
                lines.append(f"- {zh_names[keys[i]]} +{delta}")
        lines.append(f"✅ 達成獎勵：{label}（final_score = {achieved_score}）")

    future_rewards = [t for t in reward_thresholds if achieved_score < t[0]]
    if future_rewards:
        lines.append("\n📌 下一階段獎勵預告：")
        for i, (threshold, label) in enumerate(future_rewards[:2], 1):
            lines.append(f"- 第 {i} 階：{label}（門檻 {threshold}）")

    return "\n".join(lines)

@bot.slash_command(name="原初", description="計算原初之星分數")
async def primal(ctx, input: str):
    await process_input(ctx, input, recommend=False)

@bot.slash_command(name="原初推薦", description="推薦原初之星提升組合")
async def primal_plus(ctx, input: str):
    await process_input(ctx, input, recommend=True)

@bot.slash_command(name="help", description="顯示使用說明")
async def help_cmd(ctx):
    await ctx.respond(get_help_text())

@bot.slash_command(name="說明", description="顯示使用說明（中文別名）")
async def help_zh(ctx):
    await ctx.respond(get_help_text())

def get_help_text():
    return (
        "**📘 原初之星計算器使用說明：**\n"
        "輸入格式：`目前分數+/等級/裝備/技能/寵物/遺物`\n"
        "例如：`650+/192/175/170/170/18`\n\n"
        "指令說明：\n"
        "`/原初`：計算原初之星分數與獎勵狀態\n"
        "`/原初推薦`：推薦最划算的提升組合\n"
        "`/help` 或 `/說明`：顯示本說明"
    )

async def process_input(ctx, input: str, recommend: bool):
    await ctx.defer()
    try:
        parts = input.split('/')
        if len(parts) != 6:
            await ctx.respond("⚠️ 輸入格式錯誤，請使用：`目前分數+/等級/裝備/技能/寵物/遺物`")
            return
        current_score = 0
        if '+' in parts[0]:
            try:
                current_score = int(parts[0].replace('+', ''))
            except:
                await ctx.respond("⚠️ 首欄目前分數格式錯誤")
                return
        result, error = calculate_score(parts[1:], current_score)
        if error:
            await ctx.respond(error)
            return
        lines = [
            f"🌟 總原初之星：{result['total_score']}",
            get_reward_status(result["total_score"])
        ]
        if not recommend:
            future_rewards = [t for t in reward_thresholds if result["final_score"] < t[0]]
            if future_rewards:
                lines.append("\n📌 下一階段獎勵預告：")
                for i, (threshold, label) in enumerate(future_rewards[:2], 1):
                    lines.append(f"- 第 {i} 階：{label}（門檻 {threshold}）")
        else:
            lines.append("\n" + recommend_upgrades(result["final_score"], result["raw"]))
        await ctx.respond("\n".join(lines))
    except Exception as e:
        await ctx.respond(f"⚠️ 發生錯誤：{str(e)}")

# 啟動 Bot
bot.run(os.environ['TOKEN'])
