# Item Bank 改写稿（保持原方向与标签）

说明：下面这版只改写题面，不改原有方向；原题库沿用 `id / prompt / dimension_weights / scenario_tags` 结构，核心维度与子维度定义见源码。

## 核心层（core）
- **core-social-1**｜方向：`social_initiative`｜标签：`study, unknown_group`  
  第一次进一个新组，桌上已经安静了半分钟，我多半会先开口把场子启动起来。
- **core-social-2**｜方向：`social_stimulation_tolerance`｜标签：`public, high_stakes`  
  群聊一旦同时冒出几条线，我通常还能跟得上，不会很快被噪声耗空。
- **core-social-3**｜方向：`social_initiative`｜标签：`online, work`  
  线上讨论刚有苗头但还没人定主线时，我常会先丢一个方向让大家接。
- **core-social-4**｜方向：`social_initiative`｜标签：`leisure, unknown_group`  
  朋友刚聚齐、节目还没着落时，我往往会先提一个可执行的玩法。
- **core-decision-1**｜方向：`autonomous_judgment`｜标签：`work, study`  
  周围人的意见已经很整齐时，我还是会先把自己的判断做出来，再决定跟不跟。
- **core-decision-2**｜方向：`autonomous_judgment`｜标签：`high_stakes, project`  
  信息没齐但窗口已经在关时，我通常能先定一个临时判断往前走。
- **core-decision-3**｜方向：`autonomous_judgment`｜标签：`project, team_mode`  
  大家都想等更稳的说法时，我往往愿意先给出一个能落地的版本。
- **core-plan-1**｜方向：`planning_preference`｜标签：`work, project`  
  事情一开动之前，我会先想把步骤、顺序和节奏理顺。
- **core-plan-2**｜方向：`planning_preference`｜标签：`project, high_stakes`  
  局面一直在变时，我也会尽量守住一条清楚的推进主线。
- **core-plan-3**｜方向：`planning_preference`｜标签：`leisure, project`  
  无论是出门、协作还是临时做事，我常会顺手把顺序和优先级排出来。
- **core-risk-1**｜方向：`risk_tolerance`｜标签：`work, high_stakes`  
  只要回报确实值得，我能接受方案里留下不小的未知数。
- **core-risk-2**｜方向：`risk_tolerance`｜标签：`creative_mode, work`  
  一个新点子只要方向对，我愿意让它先跑一段，而不是等外界验证完再说。
- **core-risk-3**｜方向：`risk_tolerance`｜标签：`leisure, creative_mode`  
  有些事正因为结果没人说得准，反而更容易让我想下场试试。
- **core-abstract-1**｜方向：`abstraction_tendency`｜标签：`study`  
  碰到新领域时，我第一反应通常是先摸清它背后的结构，而不是先背操作。
- **core-abstract-2**｜方向：`abstraction_tendency`｜标签：`chat_mode, study`  
  别人还在讲现象时，我常会顺手把问题往更一般的结构上提。
- **core-abstract-3**｜方向：`abstraction_tendency`｜标签：`chat_mode, leisure`  
  哪怕只是聊生活琐事，我也容易去想这背后有没有更普遍的模式。
- **core-novelty-1**｜方向：`novelty_seeking`｜标签：`leisure, work`  
  旧办法明明还能用，新工具或新路径出来时，我还是会被吸过去看看。
- **core-competition-1**｜方向：`competition_cooperation`｜标签：`team_mode, project`  
  团队做事时，比起“顺利做完”，我更容易被“能不能做得更强”拉起状态。
- **core-competition-2**｜方向：`competition_cooperation`｜标签：`team_mode, game`  
  合作里只要带一点较劲意味，我的投入度通常会明显上来。
- **core-emotion-1**｜方向：`emotional_stability`｜标签：`conflict, public`  
  被人打断、否掉或者当场质疑后，我一般能比较快把状态拉回来。
- **core-emotion-2**｜方向：`emotional_stability`｜标签：`conflict, work`  
  起冲突时，我大体还能把自己的情绪和要处理的事分开。
- **core-execution-1**｜方向：`execution_drive`｜标签：`project, work`  
  一旦决定要做，我通常会很快把它推成一个看得见的动作。
- **core-execution-2**｜方向：`execution_drive`｜标签：`project, high_stakes`  
  事情往前推时就算遇到阻力，我也不会轻易松掉关键步骤。
- **core-social-5**｜方向：`social_initiative`｜标签：`open_source, online`  
  第一次进开源项目讨论区、大家还在互相试探时，我常会先抛个具体问题或 patch 思路。
- **core-social-6**｜方向：`social_initiative`｜标签：`reading_group, event`  
  在读书会、工作坊这类半熟半陌生的场子里，我一般不会一直只当背景板。
- **core-social-7**｜方向：`social_initiative`｜标签：`small_circle, meeting`  
  一个小圈子聊得很热却迟迟不落下一步时，我常会把话题往可执行的地方拽。
- **core-decision-4**｜方向：`autonomous_judgment`｜标签：`small_circle, research`  
  面对一群更资深、也更懂行的人时，我也不会轻易把自己的判断交出去。
- **core-decision-5**｜方向：`autonomous_judgment`｜标签：`maker, project`  
  某个方案在圈内很流行，但要是我觉得它不适合眼前问题，我通常不会硬跟。
- **core-plan-4**｜方向：`planning_preference`｜标签：`creator, writing`  
  做播客、视频、长帖或专题时，我往往会先在脑里把结构分好层，再开始铺内容。
- **core-plan-5**｜方向：`planning_preference`｜标签：`boardgame, event`  
  哪怕只是约朋友看展、跑活动或玩桌游，我也会自然开始排顺序和时间窗。
- **core-risk-4**｜方向：`risk_tolerance`｜标签：`maker, hackathon`  
  一个方向只要足够新鲜，哪怕教程很少，我也愿意边试边把坑补出来。
- **core-risk-5**｜方向：`risk_tolerance`｜标签：`indie_game, creative_mode`  
  比起照着现成套路稳稳完成，我更容易被那种可能翻车、但成了会很新的路子吸引。
- **core-abstract-4**｜方向：`abstraction_tendency`｜标签：`forum, critical_thinking`  
  看别人争论时，我常先注意到：他们可能根本不是在同一套框架里说话。
- **core-abstract-5**｜方向：`abstraction_tendency`｜标签：`maker, gear`  
  哪怕是在聊器材、工具或玩法，我也很容易继续追问背后的方法论是什么。
- **core-novelty-2**｜方向：`novelty_seeking`｜标签：`startup, online`  
  新平台、新工作流或新圈子的最初混乱，通常不足以立刻把我劝退。
- **core-novelty-3**｜方向：`novelty_seeking`｜标签：`fandom, small_circle`  
  一个小众领域只要有自己的黑话、规矩和内部趣味，我常会被那种内部世界感吸进去。
- **core-competition-3**｜方向：`competition_cooperation`｜标签：`hackathon, game`  
  game jam、黑客松或小型竞赛里，只要出现“谁能做出更有意思的版本”，我的状态通常会被点亮。
- **core-emotion-3**｜方向：`emotional_stability`｜标签：`open_source, critique`  
  作品、观点或 patch 被当面挑毛病时，我通常还能比较快把注意力拉回问题本身。
- **core-emotion-4**｜方向：`emotional_stability`｜标签：`small_circle, public`  
  在高手很多的小圈子里发言，就算会被懂的人盯着看，我也不太会立刻缩回去。
- **core-execution-3**｜方向：`execution_drive`｜标签：`maker, prototype`  
  一个点子只要已经清楚到能试跑，我通常更想先搭个 rough 版本，而不是继续空谈。
- **core-execution-4**｜方向：`execution_drive`｜标签：`notion, knowledge_base`  
  维护知识库、整理资料或搭系统时，我不喜欢只把东西开个头就扔在那里。

## 交叉层（cross）
- **cross-social-plan-1**｜方向：`social_initiative`｜标签：`study, unknown_group, project`  
  接手陌生团队任务时，我常会一边招呼大家动起来，一边把流程先搭个骨架。
- **cross-risk-exec-1**｜方向：`execution_drive`｜标签：`work, high_stakes`  
  一个高风险方案只要值得试，我多半会尽快把它推到试跑，而不只停在讨论。
- **cross-open-source-1**｜方向：`planning_preference`｜标签：`open_source, project`  
  开源协作里，issue 已经堆着却没人拆时，我常会先把它切成几块可处理的小任务。
- **cross-reading-group-1**｜方向：`abstraction_tendency`｜标签：`reading_group, study`  
  读书会如果一直在飘感想、没人收束，我常会把分歧背后的结构先拎出来。
- **cross-rpg-1**｜方向：`social_initiative`｜标签：`rpg, boardgame`  
  跑团或桌游局一乱起来时，我往往会一边读场面，一边把队伍节奏往回拽。
- **cross-fandom-1**｜方向：`abstraction_tendency`｜标签：`fandom, analysis`  
  做设定考据或小圈子讨论时，我通常不会满足于“好玩就行”，还会追问规则能不能自洽。

## 子维度层（sub）
- **sub-social-entry-1**｜方向：`sub:entry_speed`｜标签：`unknown_group, public`  
  进到陌生场合后，我一般不会在边上观望太久才加入谈话。
- **sub-social-entry-2**｜方向：`sub:entry_speed`｜标签：`online, unknown_group`  
  新群刚加进去、气氛不算冷时，我通常很快就会发出第一条像样的话。
- **sub-social-entry-3**｜方向：`sub:entry_speed`｜标签：`leisure, unknown_group`  
  参加半熟不熟的聚会时，我不太会一直卡在“先看别人怎么聊”的状态。
- **sub-social-entry-4**｜方向：`sub:entry_speed`｜标签：`event, unknown_group`  
  线下活动被分到陌生小队时，我通常不会一直等别人先把气氛带起来。
- **sub-social-familiar-1**｜方向：`sub:familiar_expression_intensity`｜标签：`friends, leisure`  
  跟熟人在一起时，我说话的量和力度往往会明显往上走。
- **sub-social-familiar-2**｜方向：`sub:familiar_expression_intensity`｜标签：`friends, chat_mode`  
  同一件事，面对熟人时我通常会讲得更松、更活，也更有表情。
- **sub-social-familiar-3**｜方向：`sub:familiar_expression_intensity`｜标签：`friends, home`  
  跟很熟的人聊天时，我的精力通常不是被消耗，而是被带起来。
- **sub-social-familiar-4**｜方向：`sub:familiar_expression_intensity`｜标签：`friends, dinner`  
  一桌子几乎都是自己人时，我常会比平时更敢把气氛往上托。
- **sub-social-conflict-1**｜方向：`sub:conflict_speaking_threshold`｜标签：`conflict, team_mode`  
  群体里一旦出现明显分歧，只要我有判断，通常不会拖太久才开口。
- **sub-social-conflict-2**｜方向：`sub:conflict_speaking_threshold`｜标签：`conflict, work`  
  场面已经拧住而我又看得出症结时，我一般不会一直把话憋着。
- **sub-social-conflict-3**｜方向：`sub:conflict_speaking_threshold`｜标签：`study, team_mode`  
  那种大家都知道有问题却没人点破的局面，我通常很难装作没看见。
- **sub-social-conflict-4**｜方向：`sub:conflict_speaking_threshold`｜标签：`work, meeting`  
  评审会如果明显跑偏了，我倾向当场提醒，而不是拖到会后补一句。
- **sub-decision-speed-1**｜方向：`sub:low_info_decision_speed`｜标签：`high_stakes, work`  
  信息只够七成、但事情已经得往前推时，我通常不会一直卡在剩下那三成。
- **sub-decision-speed-2**｜方向：`sub:low_info_decision_speed`｜标签：`project, high_stakes`  
  一个决定继续拖下去已经开始变贵时，我一般不会无限追加信息再动。
- **sub-decision-speed-3**｜方向：`sub:low_info_decision_speed`｜标签：`work, project`  
  如果局面要求先定一个版本再迭代，我通常能把那个版本先拍下来。
- **sub-decision-speed-4**｜方向：`sub:low_info_decision_speed`｜标签：`game, high_stakes`  
  限时任务里只要再犹豫就会错过窗口，我往往能先做出一个能跑的决定。
- **sub-decision-authority-1**｜方向：`sub:authority_dependence`｜标签：`work, study`  
  就算已经有权威结论摆在那儿，我也更愿意把它当参考，而不是直接当答案。
- **sub-decision-authority-2**｜方向：`sub:authority_dependence`｜标签：`study, chat_mode`  
  哪怕某个说法来自公认靠谱的人，我也会先在自己脑子里过一遍。
- **sub-decision-authority-3**｜方向：`sub:authority_dependence`｜标签：`work, project`  
  流程和经验打架时，我未必会本能地站到流程那一边。
- **sub-decision-authority-4**｜方向：`sub:authority_dependence`｜标签：`study, reading`  
  经典书单再有名，我也会先判断它到底适不适合眼下的问题。
- **sub-decision-ambiguity-1**｜方向：`sub:ambiguity_tolerance`｜标签：`project, high_stakes`  
  方案还没长全时，我也能接受先走一步、边走边修。
- **sub-decision-ambiguity-2**｜方向：`sub:ambiguity_tolerance`｜标签：`project, work`  
  只要主方向没坏，我通常能容忍事情在半清不楚的状态下继续推进。
- **sub-decision-ambiguity-3**｜方向：`sub:ambiguity_tolerance`｜标签：`high_stakes, creative_mode`  
  如果每一步都非得看得特别清楚才肯动，我反而会觉得整件事失去速度。
- **sub-decision-ambiguity-4**｜方向：`sub:ambiguity_tolerance`｜标签：`creative_mode, startup`  
  做新东西时，要是非得先把所有未知都压平，我会觉得最好的时机已经过去了。
- **sub-exec-start-1**｜方向：`sub:start_speed`｜标签：`project, creative_mode`  
  一个想法一旦成形，我往往不需要蓄很久就能把第一步做出来。
- **sub-exec-start-2**｜方向：`sub:start_speed`｜标签：`project, team_mode`  
  别人还在讨论要不要动的时候，我常已经把第一个动作做下去了。
- **sub-exec-start-3**｜方向：`sub:start_speed`｜标签：`creative_mode, work`  
  方案哪怕还不完美，只要方向八九不离十，我就能先把起点搭起来。
- **sub-exec-start-4**｜方向：`sub:start_speed`｜标签：`leisure, project`  
  临时起意的旅行、活动或合作，我通常也能很快把第一个动作敲定。
- **sub-plan-switch-1**｜方向：`sub:switching_tendency`｜标签：`project, creative_mode`  
  一个计划刚跑出手感时，我一般不会因为新点子冒出来就立刻换轨。
- **sub-plan-switch-2**｜方向：`sub:switching_tendency`｜标签：`creative_mode, project`  
  中途出现更酷的方案时，我会先判断它是不是真值得推翻现有路径。
- **sub-plan-switch-3**｜方向：`sub:switching_tendency`｜标签：`work, project`  
  事情已经做到半截时，我不太会因为一时兴起就整盘重来。
- **sub-plan-switch-4**｜方向：`sub:switching_tendency`｜标签：`creative_mode, writing`  
  写到中段突然很想推翻重写时，我会先分辨那是洞见，还是单纯手痒。
- **sub-exec-closure-1**｜方向：`sub:closure_strength`｜标签：`project, work`  
  比起不断开新头，我更在意把已经铺开的事真正收住。
- **sub-exec-closure-2**｜方向：`sub:closure_strength`｜标签：`work, home`  
  一件事只差最后一点就能合上时，我通常很难心安理得地把它晾着。
- **sub-exec-closure-3**｜方向：`sub:closure_strength`｜标签：`project, creative_mode`  
  到了收尾阶段，我对“差不多就行”的容忍度往往会明显下降。
- **sub-exec-closure-4**｜方向：`sub:closure_strength`｜标签：`home, admin`  
  清单只剩最后几步收口动作时，我常想一鼓作气把它们合完再走。

## 模块层（module）
- **module-study-1**｜方向：`module:study_style`｜标签：`study, team_mode`  
  一起学习时，我会下意识判断此刻谁适合拆题、谁适合推进、谁适合收束。
- **module-chat-1**｜方向：`module:chat_mode`｜标签：`online, chat_mode`  
  网聊时，我通常能很快判断眼下该轻松接话，还是直接把话题往前推。
- **module-conflict-1**｜方向：`module:conflict_mode`｜标签：`conflict, work`  
  处理分歧时，我更想先把真正卡住的点找出来，而不是先争气势。
- **module-creative-1**｜方向：`module:creative_mode`｜标签：`creative_mode, leisure`  
  做创作时，我更像是在摸一个还没定型的方向，而不是照着蓝图逐项施工。
- **module-team-1**｜方向：`module:team_mode`｜标签：`team_mode, game`  
  临时组队后，我通常很快会判断这队现在该冲、该拆，还是该先稳住。
- **module-study-2**｜方向：`module:study_style`｜标签：`reading_group, research`  
  学术讨论、读书会或技术共读里，我会自然判断现在更该扩材料、收概念，还是落到具体问题。
- **module-chat-2**｜方向：`module:chat_mode`｜标签：`forum, online`  
  论坛、群聊或评论区里，我常能很快分辨此刻该抛梗、补信息，还是把讨论拉回主线。
- **module-conflict-2**｜方向：`module:conflict_mode`｜标签：`open_source, critique`  
  做 code review、设定争论或观点辩论时，我更想先找到真正的断点，而不是先赢气势。
- **module-creative-2**｜方向：`module:creative_mode`｜标签：`indie_game, creator`  
  做独立游戏、写设定、剪片子或搭世界观时，我通常会在半成形阶段持续试错，不会太早把方向封死。
- **module-team-2**｜方向：`module:team_mode`｜标签：`hackathon, event`  
  黑客松、临时项目组或活动筹备局里，我常会很快判断这拨人现在该分工、冲刺，还是先稳住。

## 锚点题（anchor）
- **anchor-social-1**｜方向：`social_initiative`｜标签：`event, unknown_group`  
  进入一个新场域后，要是一直没人起头，我通常会觉得应该有人先把局面点亮。
- **anchor-abstract-1**｜方向：`abstraction_tendency`｜标签：`study, analysis`  
  只看做法、不追背后结构，会让我觉得自己其实还没真的理解。
- **anchor-plan-1**｜方向：`planning_preference`｜标签：`work, project`  
  重要任务开始前，如果脑中没有基本结构，我会明显不踏实。
- **anchor-exec-1**｜方向：`execution_drive`｜标签：`project`  
  决定要做一件事后，我通常会很快把它推成一个能看见的起点。

## 新增建议题（补生活 / 学术 / 工作层次）
- **core-social-8**｜方向：`social_initiative`｜标签：`study, public`  
  讨论课老师抛出问题后全场短暂停住时，只要我有想法，我往往会先接第一句。
- **core-social-9**｜方向：`social_initiative`｜标签：`meeting, unknown_group`  
  第一次参加一个半陌生的协作会，如果场子一直悬着，我常会先把话题往具体问题上落。
- **core-decision-6**｜方向：`autonomous_judgment`｜标签：`research, reading`  
  两篇资料都像样、结论却相反时，我通常更愿意自己裁断，而不是先等谁来拍板。
- **core-decision-7**｜方向：`autonomous_judgment`｜标签：`work, meeting`  
  会上已经有主流意见时，只要我觉得方向不对，我一般不会因为资历差距就放弃自己的判断。
- **core-plan-6**｜方向：`planning_preference`｜标签：`home, admin`  
  一周里杂事很多时，我会先把它们装进一个顺序清楚的框架里，再开始处理。
- **core-plan-7**｜方向：`planning_preference`｜标签：`research, writing`  
  写长笔记或研究综述前，我通常会先搭章节骨架，而不是边写边找路。
- **core-risk-6**｜方向：`risk_tolerance`｜标签：`startup, project`  
  一个方向只要上限足够高，哪怕前期路径还很糊，我也愿意先压一点筹码。
- **core-abstract-6**｜方向：`abstraction_tendency`｜标签：`reading, research`  
  看论文或教程时，我会本能地区分：哪些只是技巧，哪些才是可迁移的结构。
- **core-novelty-4**｜方向：`novelty_seeking`｜标签：`maker, online`  
  新工具刚出来、文档还不成熟时，我通常也愿意亲自摸一遍它的边界。
- **core-competition-4**｜方向：`competition_cooperation`｜标签：`study, project`  
  同样是一起做事，如果能隐约看出彼此谁做得更漂亮，我的状态通常会更满。
- **core-emotion-5**｜方向：`emotional_stability`｜标签：`critique, research`  
  被老师、同伴或审稿式反馈直接指出硬伤后，我通常还能继续就事论事地改。
- **core-execution-5**｜方向：`execution_drive`｜标签：`admin, knowledge_base`  
  一个系统已经搭出雏形后，我通常会接着把命名、归档和收尾也补齐。
- **sub-social-entry-5**｜方向：`sub:entry_speed`｜标签：`study, unknown_group`  
  刚换到新的讨论桌，只要气氛不算僵，我通常很快就会把第一句说出去。
- **sub-social-conflict-5**｜方向：`sub:conflict_speaking_threshold`｜标签：`critique, meeting`  
  会里已经出现明显误解时，只要我看出来了，一般不会一直等别人先纠正。
- **sub-decision-authority-5**｜方向：`sub:authority_dependence`｜标签：`research, reading`  
  就算某篇文章被很多人当成标准答案，我也还是会先判断它有没有偷换问题。
- **sub-decision-ambiguity-5**｜方向：`sub:ambiguity_tolerance`｜标签：`startup, project`  
  项目还处在需求和路径都没完全定型的阶段时，我也能接受先做一个试探版。
- **sub-exec-start-5**｜方向：`sub:start_speed`｜标签：`research, writing`  
  想法一旦够清楚能开写，我通常会先把提纲或第一页做出来，而不是继续憋。
- **sub-plan-switch-5**｜方向：`sub:switching_tendency`｜标签：`research, project`  
  做到一半忽然冒出更优雅的方案时，我会先算切换成本，不会立刻推翻重来。
- **sub-exec-closure-5**｜方向：`sub:closure_strength`｜标签：`knowledge_base, admin`  
  资料已经整理到最后一小段时，我通常会想顺手把索引、命名和归档一起封口。
- **module-study-3**｜方向：`module:study_style`｜标签：`reading, research`  
  共读或讨论一篇材料时，我会自然判断现在更该补背景、抠定义，还是转向核心问题。
- **module-chat-3**｜方向：`module:chat_mode`｜标签：`friends, online`  
  线上聊天里，我通常能很快看出来对方此刻更需要情绪接住，还是信息推进。
- **module-conflict-3**｜方向：`module:conflict_mode`｜标签：`meeting, project`  
  协作卡住时，我更想先确认到底是目标冲突、信息缺口，还是分工失衡。
- **module-creative-3**｜方向：`module:creative_mode`｜标签：`writing, creative_mode`  
  写东西时，我常会先放出几个半成形版本互相碰撞，而不是一开始就押单一路线。
- **module-team-3**｜方向：`module:team_mode`｜标签：`project, meeting`  
  一个新团队刚开始磨合时，我通常会先判断现在最缺的是定角色、定节奏，还是定边界。
- **cross-research-1**｜方向：`abstraction_tendency + execution_drive`｜标签：`research, project`  
  研究讨论如果一直停在概念层，我常会一边抽结构，一边追问下一步到底能做成什么。
- **cross-home-admin-1**｜方向：`planning_preference + execution_drive`｜标签：`home, admin`  
  家里待办一旦开始堆积，我通常会先把它们编排成顺序，然后按块清掉。
