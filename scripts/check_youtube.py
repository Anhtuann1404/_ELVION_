"""Opt-in YouTube DOM experiment. Opens only the user-approved search and video."""
import argparse

from elvion.browser.youtube import YouTubeError, YouTubeSession, YouTubeWorkflow
from elvion.core.contracts import ConfirmationResponse


def confirm(request):
    print(request.preview)
    approved = input("Xác nhận hành động này? [có/không] ").strip().lower() in {"có", "co", "yes", "y"}
    return ConfirmationResponse(request.confirmation_id, request.action_digest, approved)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--grant", choices=["web.open"], action="append", default=[])
    args = parser.parse_args()
    session = YouTubeSession()
    try:
        workflow = YouTubeWorkflow(session)
        report, videos = workflow.search(args.query, grants=args.grant, confirm=confirm)
        if not videos:
            print(f"Tìm kiếm dừng: {report.status.value}")
            return
        for index, video in enumerate(videos, 1):
            print(f"{index}. {video.title} — {video.channel} [{video.video_id}]")
        choice = input("Chọn số video (Enter để hủy): ").strip()
        if not choice:
            return
        if not choice.isascii() or not choice.isdigit() or not 1 <= int(choice) <= len(videos):
            raise YouTubeError("YT_INVALID_SELECTION")
        report, verified = workflow.open_video(videos[int(choice)-1].handle,
                                               grants=args.grant, confirm=confirm)
        if verified:
            print("Đã mở và kiểm chứng đúng trang video. Chưa kiểm chứng phát video.")
        else:
            print(f"Chưa kiểm chứng được video đã chọn: {report.status.value}")
    except YouTubeError as error:
        print(f"Dừng: {error}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
