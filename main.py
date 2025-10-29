import math
import statistics

# 加權參數
weights = {
    "level": 100,
    "equip": 18,
    "skill": 7,
    "pet": 8,
    "relic": 33
}

multipliers = {
    "level": 1,
    "equip": 5,
    "skill": 8,
    "pet": 4,
    "relic": 20
}

season_max = {
    "level": 130,
    "equip": 650,
    "skill": 1040,
    "pet": 520,
    "relic": 260
}

zh_names = {
    "level": "等級",
    "equip": "裝備",
    "skill": "技能",
    "pet": "寵物",
    "relic": "遺物"
}

reward_thresholds = [
    (630, "副本加倍"),
    (680, "經驗加成"),
    (740, "昇華機率"),
    (800, "寶石加成"),
    (860, "副本加倍"),
    (920, "經驗加成"),
    (990, "昇華機率"),
    (1060, "寶石加成"),
    (1130, "副本加倍"),
    (1200, "經驗加成"),
    (1280, "昇華機率"),
    (1360, "寶石加成"),
    (1440, "加倍機率"),
    (1520, "經驗加成"),
    (1600, "最終獎勵")
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
        return {
            "raw": raw,
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
    step_counts = 40  # 每欄最多提升 2.0

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
            if strategy == "綜合提升":
                combos.sort(key=lambda x: x[2])
            else:
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

import discord
from discord.ext import commands

bot = commands.Bot(intents=discord.Intents.default())

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
        if len(parts) == 6:
            score_part = parts[0]
            if '+' in score_part:
                try:
                    current_score = int(score_part.replace('+', ''))
                except:
                    await ctx.respond("⚠️ 目前分數格式錯誤，請使用 `129+/...`")
                    return
                values = parts[1:]
            else:
                await ctx.respond("⚠️ 輸入格式錯誤，請使用 `目前分數+/等級/裝備/技能/寵物/遺物` 或 `等級/裝備/技能/寵物/遺物`")
                return
        elif len(parts) == 5:
            current_score = 0
            values = parts
        else:
            await ctx.respond("⚠️ 輸入欄位數錯誤，請使用 `/等級/裝備/技能/寵物/遺物` 格式")
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

@bot.slash_command(name="原初", description="計算原初之星分數與獎勵")
async def primal(ctx, input: str):
    await process_input(ctx, input, recommend=False)

@bot.slash_command(name="原初推薦", description="推薦提升策略以達成下一階獎勵")
async def primal_recommend(ctx, input: str):
    await process_input(ctx, input, recommend=True)

@bot.slash_command(name="help", description="顯示使用說明")
async def help_cmd(ctx):
    await ctx.respond(embed=get_help_embed())

@bot.slash_command(name="說明", description="顯示使用說明（中文別名）")
async def help_zh(ctx):
    await ctx.respond(embed=get_help_embed())

def get_help_embed():
    embed = discord.Embed(
        title="📘 原初之星計算器使用說明",
        description="快速計算原初之星分數，並推薦最划算的提升策略",
        color=0x4A90E2
    )
    embed.add_field(
        name="📥 輸入格式",
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
            "`/原初`：計算原初之星分數與獎勵狀態，並顯示下兩階段獎勵預告\n"
            "`/原初推薦`：推薦三種提升策略（裝備主導、遺物主導、綜合平均），每項目顯示提升量與提升後總量\n"
            "`/help` 或 `/說明`：顯示本說明"
        ),
        inline=False
    )
    embed.set_footer(text="由原初之星計算器提供 ✨")
    return embed
