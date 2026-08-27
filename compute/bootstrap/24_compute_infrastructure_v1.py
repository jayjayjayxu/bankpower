#!/usr/bin/env python3
"""Create and populate the public-evidence compute infrastructure layer.

The loader is deliberately conservative: unknown values remain NULL, planned
capacity is not promoted to operating capacity, and platform aggregates are not
counted as Shenzhen physical facilities.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".vendor"))
import pymysql


ROOT = Path(__file__).resolve().parent
VERIFIED_AT = "2026-08-25"


SOURCES = {
    "PCL_CLOUD3_POWER_ON": (
        "鹏城实验室", "“鹏城云脑Ⅲ”首期设备通电点亮 进入边建设边调试阶段",
        "https://www.pcl.ac.cn/html/1036/2025-12-31/content-4652.html", "2025-12-31", "A",
    ),
    "PCL_CLOUD_OVERVIEW": (
        "鹏城实验室", "鹏城云脑重大科技基础设施",
        "https://www.pcl.ac.cn/html/1030/2026-06-25/content-3876.html", "2026-06-25", "A",
    ),
    "SZ_SUPERCOMPUTE": (
        "深圳市科技创新局", "国家超级计算深圳中心（深圳云计算中心）",
        "https://stic.sz.gov.cn/gkmlpt/content/12/12140/post_12140481.html", "2025-04-23", "A",
    ),
    "SZ_SUPERCOMPUTE_STATUS": (
        "深圳市发展和改革委员会", "算力引擎聚势腾飞 深圳人工智能全链生态建设提质增效",
        "https://fgw.sz.gov.cn/szsfzhggwyhgkml/szsfzhggwyhgkml/qt/gzdt/content/post_12640871.html", "2026-02-10", "A",
    ),
    "SZ_AI_ACTION": (
        "深圳市工业和信息化局", "深圳市加快打造人工智能先锋城市行动方案",
        "https://gxj.sz.gov.cn/gkmlpt/content/11/11474/post_11474465.html", "2024-07-30", "A",
    ),
    "SZ_OPEN_CENTER": (
        "深圳市人民政府", "深圳加快打造超强算力集群",
        "https://www.sz.gov.cn/cn/xxgk/zfxxgj/zwdt/content/post_11136745.html", "2024-02-05", "A",
    ),
    "QH_AI_CENTER": (
        "深圳市前海管理局", "前海深港人工智能算力中心正式点亮启动",
        "https://qh.sz.gov.cn/gkmlpt/content/11/11085/mpost_11085204.html", "2024-01-04", "A",
    ),
    "SMARTCITY_LOCALITY": (
        "深圳市智慧城市科技发展集团", "深智城算力基础设施与异地智算集群公开说明",
        "https://www.smartcitysz.com/home/newsDetails?newsId=187", None, "A",
    ),
    "SZ_14K_CLUSTER": (
        "深圳市人民政府", "全国首个万卡级全栈自主可控智算集群点亮",
        "https://www.sz.gov.cn/cn/xxgk/zfxxgj/zwdt/content/post_12712072.html", "2026-03-31", "A",
    ),
    "LONGHUA_AI": (
        "深圳市人民政府", "龙华新型工业智算中心护航高质量发展",
        "https://www.sz.gov.cn/cn/xxgk/zfxxgj/gqdt/content/post_11167685.html", "2024-02-29", "A",
    ),
    "PCL_CLOUD2": (
        "鹏城实验室", "鹏城云脑Ⅱ正式启用及算力精度口径",
        "https://www.pcl.ac.cn/html/943/2020-11-17/content-3566.html", "2020-11-17", "A",
    ),
    "ZT_2025_AR": (
        "深圳市证通电子股份有限公司", "2025年年度报告",
        "https://static.cninfo.com.cn/finalpage/2026-04-25/1225180677.PDF", "2026-04-25", "A",
    ),
    "ZT_FUNDING": (
        "深圳市证通电子股份有限公司", "证通智慧光明云数据中心募投项目披露",
        "https://static.cninfo.com.cn/finalpage/2020-08-07/1208140435.PDF", "2020-08-07", "A",
    ),
    "LIHE_ESG": (
        "深圳达实智能股份有限公司", "2022年度企业发展与环境、社会及公司治理报告",
        "https://www.chn-das.com/uploadfiles/2024/05/%E8%BE%BE%E5%AE%9E%E6%99%BA%E8%83%BD%EF%BC%9A2022%E5%B9%B4%E5%BA%A6%E4%BC%81%E4%B8%9A%E5%8F%91%E5%B1%95%E4%B8%8E%E7%8E%AF%E5%A2%83%E3%80%81%E7%A4%BE%E4%BC%9A%E5%8F%8A%E5%85%AC%E5%8F%B8%E6%B2%BB%E7%90%86%E6%8A%A5%E5%91%8A.pdf",
        None, "B",
    ),
    "GDS_SZ1": (
        "开放数据中心委员会（ODCC）", "万国数据深圳一号数据中心绿色等级评估",
        "https://www.odcc.org.cn/auth/v-1125641949569024002.html", "2019-05-07", "A",
    ),
    "DC_APPROVALS": (
        "深圳证券交易所信息披露平台", "深圳数据中心项目节能审查审批记录公开材料",
        "https://static.cninfo.com.cn/finalpage/2021-08-10/1210715932.PDF", "2021-08-10", "B",
    ),
    "GLP_ACQUISITION": (
        "上海证券交易所信息披露平台", "普洛斯体系收购中航云数据（深圳）主体披露",
        "https://www.sse.com.cn/disclosure/bond/announcement/company/c/2022-03-02/4436110809726432183228222.pdf",
        "2022-03-02", "B",
    ),
    "MIIT_UNICOM": (
        "工业和信息化部", "中国联通深汕云数据中心国家绿色数据中心实践经验",
        "https://www.miit.gov.cn/jgsj/jns/gzdt/art/2021/art_3264ffa0930449f6aa9a1c263b25a20e.html",
        "2021-02-09", "A",
    ),
    "MIIT_2022_GREEN": (
        "工业和信息化部", "2022年度国家绿色数据中心名单",
        "https://wap.miit.gov.cn/zwgk/zcwj/wjfb/gg/art/2023/art_628068c73a3c415b92e88b5b42d1fce1.html",
        "2023-05-11", "A",
    ),
    "MIIT_2023_CASE": (
        "工业和信息化部", "2023年度国家绿色数据中心先进经验与典型案例",
        "https://www.miit.gov.cn/cms_files/filemanager/1226211233/attach/20244/409f2e963c674ff085568d8b8d227862.pdf",
        "2024-04-30", "A",
    ),
    "CMB_2025_ESG": (
        "招商银行股份有限公司", "招商银行2025年可持续发展报告",
        "https://english.cmbchina.com/CmbIR/ProductInfo?id=csr", "2026-04-30", "A",
    ),
    "SZAICPP_SERVICE": (
        "河套深港科技创新合作区深圳园区", "算力租赁服务：深圳市智慧城市算力统筹调度平台",
        "https://htcz.sz.gov.cn/rz/tb/kctsfw/content/post_11582038.html", "2024-09-09", "A",
    ),
    "C2NET": (
        "鹏城实验室", "中国算力网（C²NET）",
        "https://pcl.ac.cn/html/1030/2024-09-15/content-4292.html", "2024-09-15", "A",
    ),
    "STATEIOC": (
        "国家算力互联网服务平台", "国家算力互联网服务平台公开服务目录",
        "https://www.stateioc.cn/", None, "A",
    ),
    "SCNET": (
        "国家超算互联网", "国家超算互联网公开服务平台",
        "https://www.scnet.cn/", None, "A",
    ),
}


FACILITIES = [
    dict(code="SZCF001", name="鹏城云脑Ⅲ", alias="鹏城云脑III", kind="AI_COMPUTE", locality="LOCAL_SHENZHEN",
         district="光明区", operator="鹏城实验室", status="COMMISSIONING", countable=1, source="PCL_CLOUD3_POWER_ON", quality="A",
         notes="首期计算板卡已通电点亮，但公开证据仍表述为边建设边调试，不能记为完整投运。"),
    dict(code="SZCF002", name="国家超级计算深圳中心（二期）", alias="深圳超算二期", kind="SUPERCOMPUTE", locality="LOCAL_SHENZHEN",
         district="光明区", operator="国家超级计算深圳中心", status="COMMISSIONING_PARTIAL_OPERATION", countable=1,
         source="SZ_SUPERCOMPUTE_STATUS", quality="A", notes="2E级系统已持续输出算力，官方同时曾表述预计2026年全面投用。"),
    dict(code="SZCF003", name="深圳开放智算中心", alias="河套深圳开放智算中心", kind="AI_COMPUTE", locality="LOCAL_SHENZHEN",
         district="福田区", operator="深圳市智城翼云科技有限公司", status="OPERATING", countable=1,
         source="SZ_AI_ACTION", quality="A", notes="4000P为中心本地口径；不得与中心+平台超30000P调度规模相加。"),
    dict(code="SZCF004", name="前海深港人工智能算力中心", alias=None, kind="AI_COMPUTE", locality="LOCAL_SHENZHEN",
         district="前海合作区", operator="前海科创集团与商汤科技合资运营主体", status="OPERATING", countable=1,
         source="QH_AI_CENTER", quality="A", notes="一期500P FP16、一期投资4.66亿元。"),
    dict(code="SZCF005", name="万卡级全栈自主可控智算集群", alias="深智城14000P智算集群", kind="DISTRIBUTED_CLUSTER",
         locality="OUT_OF_SHENZHEN", district=None, operator="深圳市智慧城市科技发展集团相关运营体系", status="OPERATING",
         countable=0, source="SMARTCITY_LOCALITY", quality="A", notes="异地集群；不得计入深圳本地物理机房容量。"),
    dict(code="SZCF006", name="龙华新型工业智算中心", alias=None, kind="AI_COMPUTE", locality="LOCAL_SHENZHEN",
         district="龙华区", operator="深圳移动与龙华数据有限公司", status="OPERATING", countable=1,
         source="LONGHUA_AI", quality="A", notes="一期1000P已点亮，终期10000P仅为规划。"),
    dict(code="SZCF007", name="鹏城云脑Ⅱ", alias="鹏城云脑II", kind="AI_COMPUTE", locality="LOCAL_SHENZHEN",
         district=None, operator="鹏城实验室", status="OPERATING", countable=1, source="PCL_CLOUD2", quality="A",
         notes="FP16和INT8能力分行保存；不同精度不得相加。"),
    dict(code="SZCF008", name="证通智慧光明云数据中心项目", alias="证通智慧光明云数据中心", kind="IDC",
         locality="LOCAL_SHENZHEN", district="光明区", operator="深圳市证通云计算有限公司", owner="深圳市证通电子股份有限公司",
         owner_company="C000084", status="UNDER_CONSTRUCTION_OPERATION_SCOPE_UNKNOWN", countable=1, source="ZT_2025_AR", quality="A",
         notes="募投项目仍列在建；入选绿色数据中心不能反推全部1520柜均已投运。"),
    dict(code="SZCF009", name="深圳力合报业大数据中心", alias=None, kind="IDC", locality="LOCAL_SHENZHEN",
         district="龙华区", operator="深圳力合报业大数据中心有限公司", status="OPERATING", countable=1,
         source="LIHE_ESG", quality="B", notes="机柜、柜功率及PUE来自项目承包方ESG披露；合同额不等于总投资。"),
    dict(code="SZCF010", name="万国数据深圳一号数据中心", alias=None, kind="IDC", locality="LOCAL_SHENZHEN",
         district="福田区", address="福田保税区桃花路5号", operator="万国数据", operator_company="C000079",
         status="OPERATING", countable=1, source="GDS_SZ1", quality="A", notes="2014年4月投运；与其他主体的同名‘深圳一号’记录不得混同。"),
    dict(code="SZCF011", name="坪山万国数据云计算人工智能平台一期项目", alias=None, kind="IDC", locality="LOCAL_SHENZHEN",
         district="坪山区", operator="万国数据相关主体", operator_company="C000079", status="APPROVED_OPERATION_STATUS_UNKNOWN",
         countable=1, source="DC_APPROVALS", quality="B", notes="仅确认项目和节能审批记录；机柜数、功率及当前运营状态不写入正式事实。"),
    dict(code="SZCF012", name="中航云数据深圳数据传输枢纽及数据交互中心", alias=None, kind="IDC", locality="LOCAL_SHENZHEN",
         district="坪山区", operator="中航云数据（深圳）有限公司", status="APPROVED_OPERATION_STATUS_UNKNOWN", countable=1,
         source="DC_APPROVALS", quality="B", notes="仅确认项目审批存在；2022年主体并购不等于设施投运证明。"),
    dict(code="SZCF013", name="中国联通深汕云数据中心（腾讯鹅埠数据中心2号楼）", alias="中国联通深汕云数据中心",
         kind="IDC", locality="SHENSHAN", district="深汕特别合作区", operator="中国联合网络通信有限公司深圳市分公司",
         operator_company="C000080", status="OPERATING", countable=1, source="MIIT_2022_GREEN", quality="A",
         notes="腾讯楼号不代表共同运营；PUE为联通深汕云数据中心口径，不强行解释为2号楼独立值。"),
    dict(code="SZCF014", name="深圳电信深汕数据中心（腾讯鹅埠数据中心5号楼）", alias="深圳电信深汕数据中心", kind="IDC",
         locality="SHENSHAN", district="深汕特别合作区", operator="中国电信股份有限公司深圳分公司", operator_company="C000081",
         status="OPERATING", countable=1, source="MIIT_2023_CASE", quality="A",
         notes="项目级PUE、WUE、面积和年节电量缺少本轮一手证据，保持NULL。"),
    dict(code="SZCF015", name="招商银行深圳平湖数据中心", alias=None, kind="FINANCIAL_DC", locality="LOCAL_SHENZHEN",
         district="龙岗区", operator="招商银行股份有限公司", status="OPERATING", countable=1, source="CMB_2025_ESG", quality="A",
         notes="招商银行自有数据中心平均PUE属于组合口径，不能当作平湖中心实际PUE。"),
]


METRICS = [
    ("SZCF001", "COMPUTE_CAPACITY", "POWERED_ON_TEST_CAPACITY", 4500, None, None, "PFLOPS", None, "EQ", "DISCLOSED", "2025-12-29", 0, "PCL_CLOUD3_POWER_ON", "A", "通电测试，不等于正式投运。"),
    ("SZCF001", "COMPUTE_CAPACITY", "FINAL_TARGET_CAPACITY", 16000, None, None, "PFLOPS", None, "EQ", "TARGET", "2026-06-25", 0, "PCL_CLOUD_OVERVIEW", "A", "最终目标。"),
    ("SZCF002", "COMPUTE_CAPACITY", "EQUIPPED_SUSTAINED_PEAK", 2, None, None, "EFLOPS", None, "GE", "DISCLOSED", "2026-02-10", 1, "SZ_SUPERCOMPUTE_STATUS", "A", "持续计算峰值口径；精度未披露。"),
    ("SZCF003", "COMPUTE_CAPACITY", "LOCAL_CENTER_CAPACITY", 4000, None, None, "PFLOPS", None, "EQ", "DISCLOSED", "2024-07-30", 1, "SZ_AI_ACTION", "A", "深圳开放智算中心本地算力。"),
    ("SZCF004", "COMPUTE_CAPACITY", "PHASE1_OPERATING_CAPACITY", 500, None, None, "PFLOPS", "FP16", "EQ", "DISCLOSED", "2024-01-03", 1, "QH_AI_CENTER", "A", "一期已点亮。"),
    ("SZCF004", "PROJECT_INVESTMENT", "PHASE1_TOTAL_INVESTMENT", 46600, None, None, "WANYUAN", None, "EQ", "DISCLOSED", "2024-01-03", 1, "QH_AI_CENTER", "A", "一期总投资4.66亿元。"),
    ("SZCF005", "COMPUTE_CAPACITY", "TWO_PHASE_OPERATING_AGGREGATE", 14000, None, None, "PFLOPS", None, "EQ", "DISCLOSED", "2026-03-26", 0, "SZ_14K_CLUSTER", "A", "异地两期集群合计，不计深圳本地物理容量。"),
    ("SZCF005", "RESOURCE_UTILIZATION", "TWO_PHASE_OFFTAKE_RATIO", 0.92, None, None, "RATIO", None, "EQ", "DISCLOSED", "2026-03-26", 0, "SZ_14K_CLUSTER", "A", "去化率不是IT利用率或GPU实际利用率。"),
    ("SZCF006", "COMPUTE_CAPACITY", "PHASE1_OPERATING_CAPACITY", 1000, None, None, "PFLOPS", None, "EQ", "DISCLOSED", "2024-02-29", 1, "LONGHUA_AI", "A", "一期已点亮；精度未披露。"),
    ("SZCF006", "COMPUTE_CAPACITY", "FINAL_PLANNED_CAPACITY", 10000, None, None, "PFLOPS", None, "EQ", "PLANNED", "2024-02-29", 0, "LONGHUA_AI", "A", "二、三期终期规划。"),
    ("SZCF006", "LIQUID_COOLING_RATIO", "OVERALL_DESIGN", 0.50, None, None, "RATIO", None, "GT", "DISCLOSED", "2024-02-29", 1, "LONGHUA_AI", "A", "GPU服务器全部液冷，整体液冷占比超过50%。"),
    ("SZCF007", "COMPUTE_CAPACITY", "THEORETICAL_FP16", 1, None, None, "EOPS", "FP16", "EQ", "DISCLOSED", "2020-11-17", 1, "PCL_CLOUD2", "A", "与INT8口径不可相加。"),
    ("SZCF007", "COMPUTE_CAPACITY", "THEORETICAL_INT8", 2, None, None, "EOPS", "INT8", "EQ", "DISCLOSED", "2020-11-17", 1, "PCL_CLOUD2", "A", "与FP16口径不可相加。"),
    ("SZCF007", "ACCELERATOR_COUNT", "ASCEND_910_COUNT", 4096, None, None, "COUNT", None, "EQ", "DISCLOSED", "2020-11-17", 1, "PCL_CLOUD2", "A", "昇腾910处理器数量。"),
    ("SZCF008", "CABINET_COUNT", "DESIGN_CAPACITY", 1520, None, None, "CABINET", None, "EQ", "DISCLOSED", "2020-08-07", 0, "ZT_FUNDING", "A", "建设规模，不代表全部已投运。"),
    ("SZCF008", "CABINET_RATED_POWER", "DESIGN_PER_CABINET", 5, None, None, "KW_PER_CABINET", None, "EQ", "DISCLOSED", "2020-08-07", 0, "ZT_FUNDING", "A", "设计柜功率。"),
    ("SZCF008", "PROJECT_FUNDING", "PLANNED_FUNDRAISING_INPUT", 62000, None, None, "WANYUAN", None, "EQ", "DISCLOSED", "2020-08-07", 0, "ZT_FUNDING", "A", "募投拟投入金额，不等于项目实际总投资。"),
    ("SZCF009", "CABINET_COUNT", "OPERATING_PROJECT_DISCLOSURE", 2301, None, None, "CABINET", None, "APPROX", "DISCLOSED", None, 1, "LIHE_ESG", "B", "承包方ESG披露。"),
    ("SZCF009", "CABINET_RATED_POWER", "DISCLOSED_PER_CABINET", 5, None, None, "KW_PER_CABINET", None, "EQ", "DISCLOSED", None, 1, "LIHE_ESG", "B", "承包方ESG披露。"),
    ("SZCF009", "PUE", "ANNUAL_OPERATING", 1.244, None, None, "RATIO", None, "EQ", "DISCLOSED", None, 1, "LIHE_ESG", "B", "项目承包方披露的全年PUE。"),
    ("SZCF009", "CONTRACT_AMOUNT", "DAS_PROJECT_CONTRACT", 32500, None, None, "WANYUAN", None, "EQ", "DISCLOSED", None, 0, "LIHE_ESG", "B", "达实智能项目合同额，不等于数据中心总投资。"),
    ("SZCF010", "CABINET_COUNT", "OPERATING_DISCLOSURE", 1500, None, None, "CABINET", None, "GT", "DISCLOSED", "2019-05-07", 1, "GDS_SZ1", "A", "公开表述为1500多个。"),
    ("SZCF010", "BUILDING_AREA", "FACILITY_BUILDING", 15700, None, None, "SQM", None, "EQ", "DISCLOSED", "2019-05-07", 1, "GDS_SZ1", "A", "数据中心大楼建筑面积。"),
    ("SZCF013", "CABINET_COUNT", "CENTER_APPROXIMATE", 1000, None, None, "CABINET", None, "APPROX", "DISCLOSED", "2021-02-09", 1, "MIIT_UNICOM", "A", "联通深汕云数据中心整体约千架。"),
    ("SZCF013", "BUILDING_AREA", "CENTER_APPROXIMATE", 12000, None, None, "SQM", None, "APPROX", "DISCLOSED", "2021-02-09", 1, "MIIT_UNICOM", "A", "中心整体机房面积约1.2万平方米。"),
    ("SZCF013", "PUE", "CENTER_ANNUAL_2019", 1.31, None, None, "RATIO", None, "EQ", "DISCLOSED", "2019-12-31", 1, "MIIT_UNICOM", "A", "中心年均PUE；不解释为2号楼独立值。"),
    ("SZCF015", "PUE", "CMB_OWN_DC_PORTFOLIO_2025", 1.42, None, None, "RATIO", None, "EQ", "DISCLOSED", "2025-12-31", 0, "CMB_2025_ESG", "A", "招商银行自有数据中心组合平均值，禁止作为平湖中心PUE。"),
]


PLATFORMS = [
    dict(code="STATEIOC", name="国家算力互联网服务平台", operator=None, ptype="NATIONAL_SERVICE", scope="全国",
         url="https://www.stateioc.cn/", api=None, resources=1, prices=1, scheduling=1, transaction=1, source="STATEIOC",
         notes="公开资源与服务目录；平台汇总和商品列表不代表平台自有物理算力。"),
    dict(code="SCNET", name="国家超算互联网", operator=None, ptype="NATIONAL_SUPERCOMPUTE", scope="全国",
         url="https://www.scnet.cn/", api=None, resources=1, prices=1, scheduling=1, transaction=1, source="SCNET",
         notes="国家超算资源服务平台。"),
    dict(code="SZAICPP", name="深圳市智慧城市算力统筹调度平台", operator="深圳市智城翼云科技有限公司",
         ptype="CITY_SCHEDULING", scope="深圳及可调度异地资源", url="https://console.szaicpp.com/cpnportal/home",
         api="https://console.szaicpp.com/cpn/tenant/v1/recommend/list", resources=1, prices=1, scheduling=1, transaction=1,
         source="SZAICPP_SERVICE", notes="政府页面披露100+资源地、2500P智能算力；该数字是服务平台口径。"),
    dict(code="GBACPDP", name="粤港澳大湾区一体化算力服务平台", operator=None, ptype="REGIONAL_SERVICE", scope="粤港澳大湾区及异地资源",
         url="https://ai.cnix.cn/market", api=None, resources=1, prices=1, scheduling=1, transaction=1, source="SZAICPP_SERVICE",
         notes="政府页面披露5500P+算力资源和50+数算用产品；属于平台服务口径。"),
    dict(code="C2NET", name="中国算力网（C²NET）", operator="鹏城实验室", ptype="RESEARCH_NETWORK", scope="全国",
         url="https://pcl.ac.cn/html/1030/2024-09-15/content-4292.html", api=None, resources=0, prices=0,
         scheduling=1, transaction=0, source="C2NET", notes="大型算力互联与任务统一调度基础设施。"),
]


RELATIONS = [
    ("SZCF001", "C2NET", "RESEARCH_NODE", "FACILITY_PHYSICAL", 0, "PCL_CLOUD3_POWER_ON", "鹏城云脑Ⅲ将成为中国算力网核心节点之一；当前仍在建设调试。"),
    ("SZCF007", "C2NET", "RESEARCH_NODE", "FACILITY_PHYSICAL", 0, "C2NET", "鹏城云脑Ⅱ属于鹏城实验室算力网络设施。"),
    ("SZCF003", "SZAICPP", "SERVICE_NODE", "PLATFORM_AGGREGATE", 0, "SZ_OPEN_CENTER", "中心与统筹调度平台同期点亮；平台聚合规模不等于中心物理容量。"),
    ("SZCF005", "SZAICPP", "SCHEDULED", "PLATFORM_AGGREGATE", 0, "SMARTCITY_LOCALITY", "异地集群由深圳平台体系统筹；禁止纳入深圳本地物理容量。"),
]


def connect():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQL_ROOT_PASSWORD", ""),
        database=os.getenv("DB_NAME", "spdb_power_finance"), charset="utf8mb4",
        autocommit=False, cursorclass=pymysql.cursors.DictCursor,
    )


def ensure_source(cur, key):
    org, title, url, source_date, tier = SOURCES[key]
    digest = hashlib.sha256(f"{org}|{title}|{url}".encode()).hexdigest()
    cur.execute(
        """INSERT INTO data_source
           (source_org,source_title,source_url,source_date,source_tier,data_quality,
            statistical_scope,source_hash,notes)
           VALUES (%s,%s,%s,%s,%s,'VERIFIED_PUBLIC','算力设施/平台字段级公开事实',%s,
                   '2026-08-25事实核验；未知字段保持NULL。')
           ON DUPLICATE KEY UPDATE source_org=VALUES(source_org),source_title=VALUES(source_title),
             source_url=VALUES(source_url),source_date=VALUES(source_date),source_tier=VALUES(source_tier),
             data_quality=VALUES(data_quality),statistical_scope=VALUES(statistical_scope),notes=VALUES(notes)""",
        (org, title, url, source_date, tier, digest),
    )
    cur.execute("SELECT source_id FROM data_source WHERE source_hash=%s", (digest,))
    return cur.fetchone()["source_id"]


def execute(execute_mode):
    db = connect()
    try:
        with db.cursor() as cur:
            schema = (ROOT / "build_compute_infrastructure_v1_schema.sql").read_text(encoding="utf-8")
            for statement in [s.strip() for s in schema.split(";\n") if s.strip()]:
                cur.execute(statement)
            source_ids = {key: ensure_source(cur, key) for key in SOURCES}

            for f in FACILITIES:
                cur.execute(
                    """INSERT INTO enterprise_data_center_v2
                       (facility_code,operator_company_id,owner_company_id,region_id,official_name,facility_alias,
                        facility_kind,locality_scope,province_name,city_name,district_name,address_text,
                        operator_name,owner_name,lifecycle_status,physical_capacity_countable,primary_source_id,
                        last_verified_date,data_type,data_quality,notes,model_version)
                       VALUES (%s,%s,%s,56,%s,%s,%s,%s,'广东省',%s,%s,%s,%s,%s,%s,%s,%s,%s,'PUBLIC',%s,%s,'V2.0')
                       ON DUPLICATE KEY UPDATE operator_company_id=VALUES(operator_company_id),owner_company_id=VALUES(owner_company_id),
                         region_id=VALUES(region_id),official_name=VALUES(official_name),facility_alias=VALUES(facility_alias),
                         facility_kind=VALUES(facility_kind),locality_scope=VALUES(locality_scope),city_name=VALUES(city_name),
                         district_name=VALUES(district_name),address_text=VALUES(address_text),operator_name=VALUES(operator_name),
                         owner_name=VALUES(owner_name),lifecycle_status=VALUES(lifecycle_status),
                         physical_capacity_countable=VALUES(physical_capacity_countable),primary_source_id=VALUES(primary_source_id),
                         last_verified_date=VALUES(last_verified_date),data_quality=VALUES(data_quality),notes=VALUES(notes)""",
                    (f["code"], f.get("operator_company"), f.get("owner_company"), f["name"], f.get("alias"), f["kind"],
                     f["locality"], "深圳市" if f["locality"] != "OUT_OF_SHENZHEN" else None, f.get("district"), f.get("address"),
                     f.get("operator"), f.get("owner"), f["status"], f["countable"], source_ids[f["source"]], VERIFIED_AT,
                     f["quality"], f["notes"]),
                )

            cur.execute("SELECT facility_code,facility_v2_id FROM enterprise_data_center_v2")
            facility_ids = {r["facility_code"]: r["facility_v2_id"] for r in cur.fetchall()}

            for code, metric_code, scope, value, upper, text, unit, precision, operator, status, as_of, usable, source, grade, notes in METRICS:
                cur.execute(
                    """INSERT INTO compute_facility_metric_v1
                       (facility_v2_id,metric_code,metric_scope,metric_value,metric_value_upper,metric_text,metric_unit,
                        compute_precision,value_operator,disclosure_status,as_of_date,statistical_scope,
                        usable_for_facility_model,source_id,evidence_grade,data_quality,notes,model_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'V1.0')
                       ON DUPLICATE KEY UPDATE metric_value=VALUES(metric_value),metric_value_upper=VALUES(metric_value_upper),
                         metric_text=VALUES(metric_text),metric_unit=VALUES(metric_unit),compute_precision=VALUES(compute_precision),
                         value_operator=VALUES(value_operator),disclosure_status=VALUES(disclosure_status),as_of_date=VALUES(as_of_date),
                         statistical_scope=VALUES(statistical_scope),usable_for_facility_model=VALUES(usable_for_facility_model),
                         evidence_grade=VALUES(evidence_grade),data_quality=VALUES(data_quality),notes=VALUES(notes)""",
                    (facility_ids[code], metric_code, scope, value, upper, text, unit, precision, operator, status, as_of,
                     f"{code}:{scope}", usable, source_ids[source], grade, grade, notes),
                )

            for p in PLATFORMS:
                cur.execute(
                    """INSERT INTO compute_service_platform_v1
                       (platform_code,platform_name,operator_name,platform_type,service_scope,website_url,public_api_url,
                        resource_listing_public,price_public,scheduling_capability,transaction_capability,
                        physical_capacity_owner_flag,primary_source_id,as_of_date,data_quality,notes,model_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,'A',%s,'V1.0')
                       ON DUPLICATE KEY UPDATE platform_name=VALUES(platform_name),operator_name=VALUES(operator_name),
                         platform_type=VALUES(platform_type),service_scope=VALUES(service_scope),website_url=VALUES(website_url),
                         public_api_url=VALUES(public_api_url),resource_listing_public=VALUES(resource_listing_public),
                         price_public=VALUES(price_public),scheduling_capability=VALUES(scheduling_capability),
                         transaction_capability=VALUES(transaction_capability),primary_source_id=VALUES(primary_source_id),
                         as_of_date=VALUES(as_of_date),data_quality=VALUES(data_quality),notes=VALUES(notes)""",
                    (p["code"], p["name"], p["operator"], p["ptype"], p["scope"], p["url"], p["api"], p["resources"],
                     p["prices"], p["scheduling"], p["transaction"], source_ids[p["source"]], VERIFIED_AT, p["notes"]),
                )

            cur.execute("SELECT platform_code,platform_id FROM compute_service_platform_v1")
            platform_ids = {r["platform_code"]: r["platform_id"] for r in cur.fetchall()}
            for facility_code, platform_code, relation_type, capacity_scope, include_local, source, notes in RELATIONS:
                cur.execute(
                    """INSERT INTO compute_facility_platform_relation_v1
                       (facility_v2_id,platform_id,relation_type,capacity_scope,relation_status,
                        included_in_local_capacity_total,as_of_date,source_id,evidence_grade,notes,model_version)
                       VALUES (%s,%s,%s,%s,'VERIFIED',%s,%s,%s,'A',%s,'V1.0')
                       ON DUPLICATE KEY UPDATE capacity_scope=VALUES(capacity_scope),relation_status=VALUES(relation_status),
                         included_in_local_capacity_total=VALUES(included_in_local_capacity_total),as_of_date=VALUES(as_of_date),
                         source_id=VALUES(source_id),evidence_grade=VALUES(evidence_grade),notes=VALUES(notes)""",
                    (facility_ids[facility_code], platform_ids[platform_code], relation_type, capacity_scope,
                     include_local, VERIFIED_AT, source_ids[source], notes),
                )

            for f in FACILITIES:
                for field in ("official_name", "lifecycle_status", "locality_scope"):
                    value = {"official_name": f["name"], "lifecycle_status": f["status"], "locality_scope": f["locality"]}[field]
                    cur.execute(
                        """INSERT INTO compute_field_evidence_v1
                           (object_type,object_code,field_name,field_value_text,source_id,evidence_grade,
                            verification_status,verified_at,notes,model_version)
                           VALUES ('FACILITY',%s,%s,%s,%s,%s,'VERIFIED',%s,%s,'V1.0')
                           ON DUPLICATE KEY UPDATE field_value_text=VALUES(field_value_text),evidence_grade=VALUES(evidence_grade),
                             verification_status=VALUES(verification_status),verified_at=VALUES(verified_at),notes=VALUES(notes)""",
                        (f["code"], field, value, source_ids[f["source"]], f["quality"], VERIFIED_AT, f["notes"]),
                    )

            counts = {}
            for table in ("enterprise_data_center_v2", "compute_facility_metric_v1", "compute_service_platform_v1",
                          "compute_facility_platform_relation_v1", "compute_field_evidence_v1"):
                cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
                counts[table] = cur.fetchone()["c"]

        if execute_mode:
            db.commit()
        else:
            db.rollback()
        print(("COMMIT" if execute_mode else "DRY-RUN ROLLBACK"), counts)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="commit changes; default is transactional dry-run")
    args = parser.parse_args()
    execute(args.execute)
