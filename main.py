import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import math
import os
import statistics
import json
import random
from datetime import datetime
from discord import Option

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

# 卦象敘述載入
def load_hexagram_descriptions():
    try:
        with open("hexagram_descriptions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 卦象說明載入失敗：{e}")
        return {}

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

def recommend_upgrades(current_final_score, raw):
    next_targets = [t for t in reward_thresholds if current_final_score < t[0]]
    if not next_targets:
        return "🎉 已達成所有獎勵！"
    next_score = next_targets[0][0]
    keys = ["level", "equip", "skill", "pet", "relic"]
    value_table = {key: weights[key] * multipliers[key] for key in keys}
    step_table = {key: 1 / multipliers[key] for key in keys}
    step_counts = 40
    from itertools import product
    step_ranges = {
        key: [round(i * step_table[key], 3) for i in range(step_counts + 1)]
        for key in keys
    }
    strategy_weights = {
        "裝備主導": {"equip": 3},
        "遺物主導": {"relic": 3},
        "綜合提升": {}
    }
    combos_by_strategy = {}
    for strategy, bias in strategy_weights.items():
        combos = []
        for deltas in product(*[step_ranges[k] for k in keys]):
            test_raw = raw.copy()
            for i, key in enumerate(keys):
                test_raw[key] += deltas[i]
            test_parts = [str(test_raw[k]) for k in keys]
            result, _ = calculate_score(test_parts, 0)
            if result and result["final_score"] >= next_score:
                if strategy == "綜合提升":
                    stddev = statistics.stdev(deltas)
                    combos.append((deltas, result["final_score"], stddev))
                else:
                    total_value = sum(
                        deltas[i] * value_table[keys[i]] * bias.get(keys[i], 1)
                        for i in range(5)
                    )
                    combos.append((deltas, result["final_score"], -total_value))
        if combos:
            combos.sort(key=lambda x: x[2])
            combos_by_strategy[strategy] = combos[0]
    if not combos_by_strategy:
        return f"⚠️ 無法在每欄最多提升 2.0 的範圍內達成 {next_score} 分"
    lines = [f"🔍 三種推薦策略（達成 {next_score} 分）："]
    for label, (deltas, achieved_score, _) in combos_by_strategy.items():
        reward = next(t[1] for t in reward_thresholds if achieved_score >= t[0])
        lines.append(f"\n🎯 {label}：")
        for i, delta in enumerate(deltas):
            if delta > 0:
                key = keys[i]
                new_value = raw[key] + delta
                lines.append(f"- {zh_names[key]} +{delta:.3f} → {new_value:.3f}")
        lines.append(f"✅ 達成獎勵：{reward}")
    future_rewards = [t for t in reward_thresholds if achieved_score < t[0]]
    if future_rewards:
        lines.append("\n📌 下一階段獎勵預告：")
        for i, (threshold, label) in enumerate(future_rewards[:2], 1):
            lines.append(f"- 第 {i} 階：{label}（門檻 {threshold}）")
    return "\n".join(lines)

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

        lines = [
            f"⭐ 原初之星：{result['final_score']} 分",
            f"📊 總分（含目前）：{result['total_score']} 分",
            get_reward_status(result['total_score'])
        ]

        if recommend:
            lines.append("\n" + recommend_upgrades(result['final_score'], result['raw']))

        await ctx.respond("\n".join(lines))
    except Exception as e:
        await ctx.respond(f"⚠️ 發生錯誤：{str(e)}")

@bot.slash_command(name="原初", description="計算原初之星分數")
async def calc(ctx, input: Option(str, "格式：等級/裝備/技能/寵物/遺物 或 +目前分數/等級/裝備/技能/寵物/遺物")):
    await process_input(ctx, input, recommend=False)

@bot.slash_command(name="原初推薦", description="推薦如何提升原初之星")
async def recommend(ctx, input: Option(str, "格式同 /原初")):
    await process_input(ctx, input, recommend=True)

@bot.slash_command(name="原初獎勵", description="查詢原初之星獎勵階段")
async def rewards(ctx):
    lines = ["🎯 原初之星獎勵階段："]
    for threshold, label in reward_thresholds:
        lines.append(f"- {threshold} 分：{label}")
    await ctx.respond("\n".join(lines))

@bot.slash_command(name="今日造型", description="根據卦象推薦副本造型")
async def today_style(ctx):
    await ctx.defer()
    hexagrams = load_hexagram_descriptions()
    if not hexagrams:
        await ctx.respond("⚠️ 無法載入卦象敘述，請確認 hexagram_descriptions.json 是否存在")
        return
    keys = list(hexagrams.keys())
    today = datetime.now().strftime("%Y%m%d")
    seed = int(today)
    random.seed(seed)
    selected = random.choice(keys)
    descriptions = hexagrams[selected]
    lines = [f"🔮 今日卦象：**{selected}**"]
    for i, desc in enumerate(descriptions, 1):
        lines.append(f"{i}. {desc}")
    await ctx.respond("\n".join(lines))

@bot.slash_command(name="隨機", description="從選項中隨機選一個")
async def random_choice(ctx, options: Option(str, "以 / 分隔選項（最多 20 個）")):
    items = [o.strip() for o in options.split('/') if o.strip()]
    if len(items) < 2:
        await ctx.respond("⚠️ 請提供至少兩個選項，以 `/` 分隔")
        return
    if len(items) > 20:
        await ctx.respond("⚠️ 最多只能提供 20 個選項")
        return
    choice = random.choice(items)
    await ctx.respond(f"🎲 隨機選擇：**{choice}**")

@bot.slash_command(name="隨機多選", description="從選項中隨機選擇多個")
async def random_multi(ctx,
    options: Option(str, "以 / 分隔選項（最多 20 個）"),
    count: Option(int, "要選幾個", min_value=1, max_value=20)
):
    items = [o.strip() for o in options.split('/') if o.strip()]
    if len(items) < count:
        await ctx.respond(f"⚠️ 選項不足，你提供了 {len(items)} 個，但要求選 {count} 個")
        return
    if len(items) > 20:
        await ctx.respond("⚠️ 最多只能提供 20 個選項")
        return
    selected = random.sample(items, count)
    await ctx.respond(f"🎲 隨機選出 {count} 個：\n- " + "\n- ".join(selected))

@bot.slash_command(name="說明", description="顯示所有指令說明")
async def help(ctx):
    lines = [
        "📘 指令說明：",
        "/原初：計算原初之星分數",
        "/原初推薦：推薦如何提升原初之星",
        "/原初獎勵：查看原初獎勵階段",
        "/今日造型：根據卦象推薦副本造型",
        "/隨機：從選項中隨機選一個（用 `/` 分隔）",
        "/隨機多選：從選項中隨機選多個",
        "/說明：顯示這份說明"
    ]
    await ctx.respond("\n".join(lines))

# 啟動機制
bot.run(os.getenv("DISCORD_TOKEN"))
