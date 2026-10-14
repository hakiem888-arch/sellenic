
def opportunity_score(video):
    views = float(video.get("views",0))
    vph = float(video.get("vph",0))
    seo = float(video.get("seo_score",0))

    score = min(
        30 +
        min(vph/100,40) +
        min(views/1000000*20,20) +
        seo*0.1,
        100
    )

    return round(score,1)
