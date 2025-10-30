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
import re

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

def is_pure_number(s):
    return re.fullmatch(r"\d+(\.\d+)?", s) is not None
    
def calculate_score(parts, current_score):
    try:
        keys = ["level", "equip", "skill", "pet", "relic"]
        raw = {}
        adj = {}
        excess = {}
        weighted = {}

        for i, key in enumerate(keys):
            expr = parts[i]
            value = safe_eval(expr)
            raw[key] = value

            if is_pure_number(expr):
                adj[key] = value * multipliers[key]
                excess[key] = max(0, adj[key] - season_max[key])
                weighted[key] = excess[key] * weights[key]
            else:
                # 運算式欄位不進行加權
                adj[key] = value
                excess[key] = max(0, adj[key] - season_max[key] * multipliers[key])
                weighted[key] = excess[key] * weights[key]

        total = sum(weighted.values())
        final_score = math.floor(total / 27 + 45)
        total_score = final_score + current_score

        return {
            "raw": raw,
            "adj": adj,
            "excess": excess,
            "weighted": weighted,
            "final_score": final_score,
            "total_score": total_score
        }, None
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

@bot.slash_command(name="今日造型", description="看看今天各幫的副本運勢")
async def today_style(ctx):
    import random
    from datetime import datetime

    username = ctx.user.name
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    hour = now.hour

    # 時辰判定
    def get_chinese_hour(hour):
        table = [
            ("子", 23, 1), ("丑", 1, 3), ("寅", 3, 5), ("卯", 5, 7),
            ("辰", 7, 9), ("巳", 9, 11), ("午", 11, 13), ("未", 13, 15),
            ("申", 15, 17), ("酉", 17, 19), ("戌", 19, 21), ("亥", 21, 23)
        ]
        for name, start, end in table:
            if start <= hour < end or (start > end and (hour >= start or hour < end)):
                return name
        return "未知"

    chinese_hour = get_chinese_hour(hour)
    seed = f"{username}-{date_str}-{chinese_hour}"
    rng = random.Random(seed)

    # 六爻 → 八卦轉換
    def to_trigram_name(triple):
        binary = tuple(1 if x % 2 == 1 else 0 for x in triple)
        mapping = {
            (1, 1, 1): "乾", (0, 0, 0): "坤", (1, 0, 0): "震", (0, 1, 1): "巽",
            (0, 1, 0): "坎", (1, 0, 1): "離", (0, 0, 1): "艮", (1, 1, 0): "兌"
        }
        return mapping.get(binary, "未知")

    lines = [rng.randint(6, 9) for _ in range(6)]
    lower = tuple(lines[:3])
    upper = tuple(lines[3:])
    lower_name = to_trigram_name(lower)
    upper_name = to_trigram_name(upper)
    hexagram_key = f"{lower_name}下{upper_name}上"

    # 卦象名稱對照（可擴充）
    hexagram_names = {
        "乾下乾上": "乾卦", "坤下坤上": "坤卦", "坎下震上": "屯卦", "艮下坎上": "蒙卦",
        "坎下乾上": "需卦", "乾下坎上": "訟卦", "坤下坎上": "師卦", "坎下坤上": "比卦",
        "巽下乾上": "小畜卦", "乾下兌上": "履卦", "坤下乾上": "泰卦", "乾下坤上": "否卦",
        "乾下離上": "同人卦", "離下乾上": "大有卦", "坤下艮上": "謙卦", "震下坤上": "豫卦",
        "兌下震上": "隨卦", "艮下巽上": "蠱卦", "坤下兌上": "臨卦", "巽下坤上": "觀卦",
        "離下震上": "噬嗑卦", "艮下離上": "賁卦", "艮下坤上": "剝卦", "坤下震上": "復卦",
        "乾下震上": "無妄卦", "艮下乾上": "大畜卦", "艮下震上": "頤卦", "兌下巽上": "大過卦",
        "坎下坎上": "習坎卦", "離下離上": "離卦", "兌下艮上": "咸卦", "震下巽上": "恒卦",
        "乾下艮上": "遯卦", "震下乾上": "大壯卦", "離下坤上": "晉卦", "坤下離上": "明夷卦",
        "巽下離上": "家人卦", "離下兌上": "睽卦", "坎下艮上": "蹇卦", "震下坎上": "解卦",
        "艮下坤上": "損卦", "巽下震上": "益卦", "乾下兌上": "夬卦", "乾下巽上": "姤卦",
        "坤下兌上": "萃卦", "坤下巽上": "升卦", "坎下兌上": "困卦", "坎下巽上": "井卦",
        "離下兌上": "革卦", "離下巽上": "鼎卦", "震下震上": "震卦", "艮下艮上": "艮卦",
        "巽下艮上": "漸卦", "兌下巽上": "歸妹卦", "震下離上": "豐卦", "離下震上": "旅卦",
        "巽下巽上": "巽卦", "兌下兌上": "兌卦", "巽下坎上": "渙卦", "坎下巽上": "節卦",
        "兌下離上": "中孚卦", "震下艮上": "小過卦", "坎下離上": "既濟卦", "離下坎上": "未濟卦"
    }

    hexagram_title = hexagram_names.get(hexagram_key, f"{hexagram_key}（未知卦）")

    # 載入卦象敘述 JSON
    hexagram_descriptions = load_hexagram_descriptions()
    hexagram_text = rng.choice(hexagram_descriptions.get(hexagram_key, [f"{hexagram_key}：今日副本運勢平穩。"]))
    
    # 將六句以逗號分隔，並每兩句合併為一行
    segments = hexagram_text.split("，")
    hexagram_text = "\n".join(["，".join(segments[i:i+2]) for i in range(0, len(segments), 2)])
    
    # 幫派與 emoji
    styles = ["蒙眼幫", "眼鏡幫", "鐮刀幫", "不入幫"]
    style_emojis = {"蒙眼幫": "🫣", "眼鏡幫": "👓", "鐮刀幫": "🪓", "不入幫": "🙈"}

    # 加權表
    from hexagram_weights import hexagram_weights
    
    base_probs = {"double": 25, "red": 2, "ascend": 5}
    result_lines = []

    for style in styles:
        weights = hexagram_weights.get(hexagram_key, {}).get(style, {"double": 0, "red": 0, "ascend": 0})
        double_p = base_probs["double"] + weights["double"]
        red_p = base_probs["red"] + weights["red"]
        ascend_p = base_probs["ascend"] + weights["ascend"]

        double_count = red_gold_count = ascend_gold_count = 0
        for _ in range(4):
            if rng.random() < double_p / 100: double_count += 1
            if rng.random() < red_p / 100: red_gold_count += 1
            if rng.random() < ascend_p / 100: ascend_gold_count += 1

        line = f"{style_emojis[style]} {style}｜加倍：{double_count}｜紅金：{red_gold_count}｜昇華：{ascend_gold_count}"
        result_lines.append(line)

    embed = discord.Embed(
        title="🎭 今日造型報告",
        description=(
            f"👤 使用者：{username}\n📅 {now.strftime('%Y/%m/%d')}（{chinese_hour}時）\n\n"
            "🫣 蒙眼幫｜👓 眼鏡幫｜🪓 鐮刀幫｜🙈 不入幫\n"
            "✅ 加倍效果｜✨ 紅金裝｜🌟 昇華金裝\n\n"
            f"🔮 卦象：{hexagram_title}（{hexagram_text}）"
        ),
        color=0x8E44AD
    )
    embed.add_field(name="📊 四幫派副本運勢", value="\n".join(result_lines), inline=False)
    embed.set_footer(text="原初之星造型系統 ✨")
    await ctx.respond(embed=embed)

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
