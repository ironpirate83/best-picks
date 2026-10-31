# Best Picks

A small static Amazon Associates catalog: Home & Kitchen, Outdoor & Lake, and Racing Gear. Plain HTML and CSS, generated from one product file.

## Preview locally

```bash
python3 build.py
python3 -m http.server -d dist 8080
```

Open `http://127.0.0.1:8080/`.

## Refresh the picks

Edit `data/products.json`. Each product needs a brand, name, 10-character ASIN, and a one- or two-sentence blurb. Do not add prices, star ratings, or review counts. The Associates tag lives only in `site-config.json` under `associatesTag`. Run `python3 build.py` again before publishing.

## Publish on GitHub Pages

The workflow in `.github/workflows/pages.yml` builds `dist/` and deploys it when `main` changes. After this branch is merged:

1. Open the repository on GitHub: `ironpirate83/best-picks`.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Open the **Actions** tab. The workflow **Deploy to GitHub Pages** runs on every push to `main`. If it has not run, open that workflow and choose **Run workflow**.
5. When the deploy job succeeds, the site is at [https://ironpirate83.github.io/best-picks/](https://ironpirate83.github.io/best-picks/).

The repository needs to be public for GitHub Pages on a free plan. The first deploy can also ask you to allow the `github-pages` environment; approve it if GitHub prompts you.

## What the pages do

Every page shows the Associates disclosure at the top and again in the footer. Every product link goes straight to `amazon.com/dp/ASIN/` with the tag on the query string, `rel="sponsored nofollow noopener"`, and `target="_blank"`. The full destination is printed on the link. There are no prices, scores, invented testimonials, or brand logos.
