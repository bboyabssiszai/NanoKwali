---
name: video-generation
description: Turn ideas or scripts into AI video generation prompts, shot plans, and model-ready video creation packages.
metadata: {"nanobot":{"emoji":"🎬"}}
---

# Video Generation

Use this skill when the user wants to generate video content with AI video tools or needs prompts for video generation models.

## When To Use

Use this skill when the user asks for things like:

- 生成视频
- 文生视频
- 图生视频
- 给我视频 prompt
- 做一段广告视频
- 把脚本变成视频镜头
- 给可灵 / Runway / Pika / Veo 用的提示词

## Core Goal

Transform rough creative intent into a model-ready video generation package.

Do not stop at vague inspiration. Produce assets that can be pasted into video generation tools directly.

## Recommended Workflow

1. Identify the video goal:
   - ad
   - story clip
   - cinematic mood piece
   - product demo
   - food video
   - talking-head enhancement

2. Clarify the visual direction:
   - subject
   - setting
   - action
   - camera movement
   - lighting
   - style
   - duration
   - aspect ratio

3. Produce a generation package.

## Default Output Package

When the user asks for video generation help, prefer this structure:

- Video Intent
- Visual Style
- Shot Breakdown
- Master Prompt
- Negative Prompt
- Model-Specific Notes

## Prompt Writing Rules

Good video prompts should clearly specify:

- main subject
- action
- scene/environment
- camera language
- lighting
- mood
- visual style
- pacing
- aspect ratio if needed

Prefer dense, visual, specific language.

Avoid:

- abstract-only descriptions
- conflicting camera instructions
- too many unrelated subjects
- overly long narrative paragraphs with no visual guidance

## Useful Camera Language

Use terms like:

- close-up
- medium shot
- wide shot
- overhead shot
- tracking shot
- dolly in
- handheld
- slow push-in
- orbit shot
- rack focus

## Useful Style Language

Use styles like:

- cinematic realism
- food commercial
- glossy product ad
- documentary handheld
- dreamy soft light
- neon night scene
- high-contrast editorial
- warm lifestyle photography

## For NanoKwali

For this project, use this skill to help the user:

- turn short-video scripts into AI-generated scene prompts
- generate food video prompts, ad prompts, and social-media video prompts
- break a concept into 3-6 shots for separate generation
- adapt output for different video models

## Model Adaptation

When useful, provide separate notes for:

- Kling / 可灵
- Runway
- Pika
- Veo
- Hailuo

If the user does not specify a model, generate a neutral high-quality prompt first, then mention how to adapt it.

## Suggested Response Shapes

- Single-Shot Prompt: for one cinematic clip
- Multi-Shot Pack: for a sequence of generated shots
- Ad Video Pack: for product or brand videos
- Food Video Pack: for barbecue, restaurant, or recipe-style visual content
