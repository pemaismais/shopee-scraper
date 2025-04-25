from src.scraper import ShopeeScraper
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True) 
    group.add_argument("-k", "--keyword", help="Search term (ignored if --product-link is used)")
    group.add_argument("-l","--product-link", help="Direct URL of the Shopee product to scrape reviews from")
    parser.add_argument("-n", "--num", type=int, default=10, help="Number of products")
    parser.add_argument("-r", "--review-limit", type=int, default=10, help="Max reviews per product")
    parser.add_argument("--index-only", action="store_true", default=False, help="If set, only retrieve index data")
    parser.add_argument("--all-star-types", action="store_true", default=False, help="Retrieve comments by filtering each star rating.")
    parser.add_argument("--star-limit-per-type", type=int, default=10, help="Number of reviews to retrieve per star type.")
    parser.add_argument("--chrome-user-data-dir", default=None, help="User data directory for Chrome")
    parser.add_argument("--media-only", action="store_true", default=False, help="Only retrieve reviews with media (images or videos).")
    parser.add_argument("-c", "--continue-scrape", action="store_true", default=False, help="Continue scraping reviews from the last saved page (only for single product link).")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output file.")

    args = parser.parse_args()

    if args.product_link:
        if args.index_only:
            print("Warning: --index-only is ignored when --product-link is used.")
            args.index_only = False 
        if args.num != parser.get_default("num"): 
            print(f"Warning: --num ({args.num}) is ignored when --product-link is used.")
        if args.all_star_types and args.media_only:
            parser.error("--all-star-types and --media-only cannot be used together.")
        scraper = ShopeeScraper(args.keyword,
                                args.num,
                                args.index_only,
                                args.review_limit,
                                all_star_types=args.all_star_types,
                                star_limit_per_type=args.star_limit_per_type,
                                chrome_user_data_dir=args.chrome_user_data_dir,
                                media_only=args.media_only,
                                product_link=args.product_link,
                                continue_scrape=args.continue_scrape,
                                output_file=args.output)
        scraper.execute()
    else:
        scraper = ShopeeScraper(args.keyword,
                                args.num,
                                args.index_only,
                                args.review_limit,
                                all_star_types=args.all_star_types,
                                star_limit_per_type=args.star_limit_per_type,
                                chrome_user_data_dir=args.chrome_user_data_dir,
                                media_only=args.media_only,
                                product_link=args.product_link,
                                continue_scrape=False,
                                output_file=args.output)
        scraper.execute()