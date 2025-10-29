import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import math
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Keep-alive 網頁伺服器（供 Render 使用）
app = Flask('')
@app.route('/')
def home():
    return "I'm alive!"
def run():
    app.run(host='0.0.0.0', port=8080)
Thread(target=run).start()

# Discord Bot 設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=['!', '！'], intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot 已啟動：{bot.user}")

# 參數設定
multipliers = {
    "level": 1,
    "equip": 5,
    "skill": 8,
    "pet": 4,
    "relic": 20
}
weights = {
    "level": 100,
    "equip": 18,
    "skill": 7,
    "pet": 8,
    "relic": 33
}
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

# 數值解析
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

# 分數計算
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

# 獎勵判斷
def get_reward_status(score):
    for threshold, label in reversed(reward_thresholds):
        if score >= threshold:
            return f"🎁 達成獎勵：{label}（門檻 {threshold}）"
    next_reward = next((t for t in reward_thresholds if score < t[0]), None)
    if next_reward:
        diff = next_reward[0] - score
        return f"⛔ 尚未達成獎勵，距離下一階「{next_reward[1]}」還差 {diff} 分"
    return "⛔ 尚未達成任何獎勵"

# 推薦提升組合
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

# 指令處理核心
async def process_input(ctx_or_interaction, input_str, recommend):
    parts = input_str.strip().split('/')
    keys = ["level", "equip", "skill", "pet", "relic"]

    if '+' in parts[0]:
        try:
            current_score = int(eval(parts[0].replace('+', '')))
        except:
            await ctx_or_interaction.response.send_message("❗ 無法解析上季末總原初表達式")
            return
        parts = parts[1:]
    else:
        current_score = 0
        if len(parts) == 6:
            parts = parts[1:]

    if len(parts) != 5:
        await ctx_or_interaction.response.send_message("❗ 請輸入格式為 [上季末總原初+]/等級/裝備/技能/寵物/遺物")
        return

    result, error = calculate_score(parts, current_score)
    if error:
        await ctx_or_interaction.response.send_message(error)
        return

    total_score = result["total_score"]
    lines = [
        f"🌟 總原初之星：{total_score}",
        get_reward_status(total_score)
    ]

    if recommend:
        lines.append("\n" + recommend_upgrades(total_score, result["raw"]))

    await ctx_or_interaction.response.send_message("\n".join(lines))

# 文字指令
@bot.command()
async def s2(ctx, *, input_str):
    await process_input(ctx, input_str, recommend=False)

@bot.command()
async def S2(ctx, *, input_str):
    await process_input(ctx, input_str, recommend=True)

@bot.command(name="help")
async def help_command(ctx):
    help_text = """
📘 **原初之星計算器使用說明**

指令格式：
- `/s2 等級/裝備/技能/寵物/遺物`
- `/s2 上季末總原初+/等級/裝備/技能/寵物/遺物`
- `/S2`（大寫）會額外顯示推薦提升組合

可輸入平均等級或各等級加總  
如裝備可輸入平均 169.6 或 170*3+169*2

範例：
- `/s2 /192/175/170/170/18`
-
