#!/usr/bin/env python3
"""
測試Harvard Art Museums API連接
"""

import logging

from harvard_art_museums_crawler import HarvardArtMuseumsCrawler, HarvardCrawlerConfig


def test_harvard_api():
    """測試Harvard API連接"""
    logging.basicConfig(level=logging.INFO)

    print("🚀 測試Harvard Art Museums API連接...")

    # 配置爬蟲
    config = HarvardCrawlerConfig(
        api_key="CHANGE_ME_HARVARD_API_KEY",
        delay_seconds=0.5,
        max_per_page=5,  # 測試用小數量
    )

    crawler = HarvardArtMuseumsCrawler(config)

    # 測試基本API調用
    print("\n=== 測試API端點 ===")

    # 1. 測試獲取作品數據
    print("📸 測試獲取作品數據...")
    objects_response = crawler.get_objects(page=1, size=3)
    if objects_response:
        print(f"✅ 作品API成功，獲取 {len(objects_response.get('records', []))} 個作品")
        if objects_response.get("records"):
            sample_object = objects_response["records"][0]
            print(f"   示例作品: {sample_object.get('title', 'Unknown')}")
    else:
        print("❌ 作品API失敗")

    # 2. 測試獲取人物數據
    print("\n👤 測試獲取人物數據...")
    people_response = crawler.get_people(page=1, size=3)
    if people_response:
        print(f"✅ 人物API成功，獲取 {len(people_response.get('records', []))} 個人物")
        if people_response.get("records"):
            sample_person = people_response["records"][0]
            print(f"   示例人物: {sample_person.get('displayname', 'Unknown')}")
    else:
        print("❌ 人物API失敗")

    # 3. 測試獲取展覽數據
    print("\n🖼️ 測試獲取展覽數據...")
    exhibitions_response = crawler.get_exhibitions(page=1, size=3)
    if exhibitions_response:
        print(f"✅ 展覽API成功，獲取 {len(exhibitions_response.get('records', []))} 個展覽")
        if exhibitions_response.get("records"):
            sample_exhibition = exhibitions_response["records"][0]
            print(f"   示例展覽: {sample_exhibition.get('title', 'Unknown')}")
    else:
        print("❌ 展覽API失敗")

    # 4. 測試獲取元數據
    print("\n📋 測試獲取元數據...")
    classifications = crawler.get_classifications()
    if classifications:
        print(f"✅ 分類數據成功，獲取 {len(classifications.get('records', []))} 個分類")
    else:
        print("❌ 分類數據失敗")

    # 5. 獲取樣本數據並保存
    print("\n💾 獲取樣本數據...")
    crawler.get_sample_data()

    print("\n📊 API調用統計:")
    print(f"   總調用次數: {crawler.api_calls_count}")
    print(f"   剩餘調用次數: {config.daily_limit - crawler.api_calls_count}")

    print("\n🎉 Harvard Art Museums API測試完成！")


if __name__ == "__main__":
    test_harvard_api()
