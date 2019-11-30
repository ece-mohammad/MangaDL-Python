#!/usr/bin/env python3


# -----------------------------------------------------------------------------

from urllib import request
from urllib import error
from urllib import parse
from http import cookiejar
from bs4 import BeautifulSoup as Soup
import time
import os
import sys
import logging as log
from socket import timeout as TimeoutException
import pickle

# -----------------------------------------------------------------------------

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " \
              "AppleWebKit/537.36 (KHTML, like Gecko) " \
              "Chrome/76.0.3809.132 Safari/537.36 OPR/63.0.3368.107"

_ACCEPT_ENCODING = "deflate"

_INFO = log.INFO
_DEBUG = log.DEBUG
_ERROR = log.ERROR
_CRITICAL = log.CRITICAL

# -----------------------------------------------------------------------------


class MangaReader(object):

    def __init__(self, manga_url, target_dir='.', debug_level=_DEBUG, wait_time=5, time_out=10, retries=3, retry_after=10):

        manga_url = manga_url.strip("/")

        self._logger = log.getLogger("MangaReader")
        self._logger_format = '[%(asctime)s-%(name)s]:%(message)s'
        log.basicConfig(format=self._logger_format, level=debug_level, stream=sys.stdout)

        self._base_address = 'http://www.mangareader.net/'
        self._logger.info("Starting Crawler for {}".format(manga_url))
        self._manga_url = manga_url
        self._target_dir = target_dir

        self.make_dir_tree(self._target_dir)
        os.chdir(self._target_dir)
        self._logger.info("Moving into directory: {}".format(self._target_dir))

        if not self.validate_url(manga_url):
            raise ValueError

        self._manga_name = parse.urlparse(self._manga_url).path.strip("/")

        self.__cookie_jar = cookiejar.CookieJar()
        self.__cookie_processor = request.HTTPCookieProcessor(self.__cookie_jar)
        self._req_opener = request.build_opener(self.__cookie_processor)
        self._req_opener.addheaders = [("User-Agent", _USER_AGENT), ("Accept-Encoding", _ACCEPT_ENCODING)]

        self._time_out = time_out
        self._retry_count = retries if retries > 0 else 3

        self._available_chapters = dict()
        self._current_dir = os.path.abspath(os.getcwd())

        self._total_req_count = 0
        self._total_bytes = 0
        self._wait_time = wait_time if wait_time > 0 else 5
        self._retry_after = retry_after if retry_after > 0 else 10
        self._next_request_time = (time.time() + self._wait_time)

    @property
    def available_chapters(self):
        """
        Getter for available_chapters attribute
        :return: (list[str]) available_chapters attribute value
        """
        return self._available_chapters

    @property
    def manga_url(self):
        """
        Getter for managa_url attribute
        :return: (str) manga_url attribute value
        """
        return self._manga_url

    @manga_url.setter
    def manga_url(self, new_url):
        """
        setter for manga_url attribute
        :param new_url:(str)  manga URL
        :return: None
        """
        self._manga_url = new_url
        self._logger.debug("Setting manga url to: {}".format(new_url))

    @property
    def target_dir(self):
        """
        Getter for target_dir attribute
        :return: (str) target_dir value
        """
        return self._target_dir

    @target_dir.setter
    def target_dir(self, new_dir):
        """
        setter for target_dir attribute
        :param new_dir: (str) new directory path (relative or absolute)
        :return: None
        """
        self._target_dir = new_dir
        self._logger.debug("Setting target directory to: {}".format(new_dir))

    def make_dir_tree(self, dir_path):
        """
        Build directory hierarchy pointed to by dir_path
        :param dir_path: (str) path (absolute or relative) to a directory (folder)
        :return: None
        """
        if os.path.isabs(dir_path):
            path_drive, dir_hierarchy = os.path.splitdrive(dir_path)
            if not os.path.exists(path_drive):
                self._logger.critical("Can't create folder, drive {} doesn't exist!".format(path_drive))
            else:
                os.chdir(path_drive+os.path.sep)

        path_components = dir_path.split(os.path.sep)
        for folder in path_components:
            if not os.path.isdir(folder):
                os.mkdir(folder)
                self._logger.debug("Created folder: {}".format(folder))
            os.chdir(folder)

        self._logger.info("Created folder: {}".format(dir_path))

    def validate_url(self, url):
        """
        Validates given URL. Makes sure the given URL belongs to mangareder.net domain, and is a manga's main page URL.
        :param url: URL to validate (URL of manga's main page)
        :return: Boolean
        True if it's a manga's main page URL, False otherwise.
        """
        self._logger.debug("Validating URL: {}".format(url))
        status = True
        parsed_url = parse.urlparse(url)

        if parsed_url.netloc != parse.urlparse(self._base_address).netloc:
            self._logger.critical("URL [{}] is not a mangareader URL!".format(url))
            status = False

        elif not parsed_url.path:
            self._logger.critical("URL [{}] points to managareader's main page, not to a manga!".format(url))
            status = False

        elif len(parsed_url.path[1:].strip("/").split("/")) > 1:
            self._logger.critical("URL [{}] is not a valid manga URL!".format(url))
            status = False

        else:
            self._logger.debug("URL [{}] is a valid manga URL.".format(url))

        return status

    def get_page_source(self, url, retry_count=3):
        """
        Try to request given URL using MangaReader request opener. And returns page HTML source.
        :param url: URL to open
        :param retry_count: remaining retries
        :return: (boolean, str)
        boolean: True if request is successful and response code is 200. False otherwise
        str : Server's response content
        """
        self._logger.debug("Trying to get url: {}".format(url))
        page_src = None
        status = False
        try:
            while time.time() < self._next_request_time:
                pass
            rsp = self._req_opener.open(url, timeout=self._time_out)
            page_src = rsp.read()
            if rsp.code == 200:
                self._total_bytes += len(page_src)
                status = True
                self._logger.debug("Request successful")
            else:
                self._logger.warning("Response code is not 200 [{}: {}]".format(rsp.code, rsp.reason))
            self._total_req_count += 1
            self._next_request_time = (time.time() + self._wait_time)

        except error.ContentTooShortError as e:
            self._logger.error("Requesting failed due to exception: {}".format(e))

        except error.HTTPError as e:
            self._logger.error("Requesting failed due to exception: {}".format(e))

        except error.URLError as e:
            self._logger.error("Requesting failed due to exception: {}".format(e))

        except TimeoutException as e:
            self._logger.error("Requesting failed due to exception: {}".format(e))

        except Exception as e:
            self._logger.error("Requesting failed due to exception: {}".format(e))

        finally:
            if not status:
                if retry_count > 0:
                    self._logger.debug("Retrying after {} seconds...".format(self._retry_after))
                    time.sleep(self._retry_after)
                    return self.get_page_source(url, (retry_count-1))
                else:
                    self._logger.critical("Can't request URL {}. Exceeded max retries".format(url))

        return status, page_src

    def get_chapter_list(self, retry_count=3):
        """
        Gets manga's available chapters from managareader (URLs and number of pages for each chapter)
        :param retry_count: Number of retries if failed at getting chapter list
        :return: None
        """
        self._logger.info("Getting list of available chapters...")
        status, page_html = self.get_page_source(self._manga_url)

        if status:
            parsed_html = Soup(page_html, "lxml")
            chapters_links = parsed_html.select("#chapterlist a")

            if chapters_links:
                for ch_num, ch_obj in enumerate(chapters_links, start=1):
                    chapter_url = ch_obj.get("href")
                    chapter_url = parse.urljoin(self._base_address, chapter_url)
                    status, page_html = self.get_page_source(chapter_url)

                    if status:
                        parsed_html = Soup(page_html, "lxml")
                        chapter_pages = parsed_html.select("div#selectpage")

                        if chapter_pages:
                            chapter_pages = int(chapter_pages[0].text.strip().split()[-1])
                            self._available_chapters[ch_num] = (chapter_url, chapter_pages)
                            self._logger.debug("Chapter {}, {} pages..".format(ch_num, chapter_pages))
                        else:
                            self._logger.critical("Failed to locate chapter {} pages count!".format(ch_num))
                            self._available_chapters[ch_num] = (chapter_url, 0)
                            raise (Exception, "Failed to locate chapter {} pages count!".format(ch_num))

                    else:
                        if retry_count > 0:
                            self._logger.critical("Failed to get chapter list info, retrying..")
                            self.get_chapter_list(retry_count=(retry_count - 1))
                        else:
                            self._logger.critical("Exceeded maximum retry count! Failed to get chapter list!")

                self._logger.info("Found {} chapter links".format(len(chapters_links)))

            else:
                self._logger.error("Failed to locate chapters' links...")

        else:
            if retry_count > 0:
                self._logger.debug("Retrying to get manga's chapter info.")
                self.get_chapter_list(retry_count=(retry_count-1))
            else:
                self._logger.critical("Exceeded maximum retry count! Failed to get chapter list!")

    def save_chapter_list(self):
        """
        Saves available chapters
        :return:
        """
        data_file = "{}.pkl".format(self._manga_name)
        if not os.path.exists(data_file):
            with open(data_file, "wb") as fh:
                pickle.dump(obj=self._available_chapters, file=fh)
        else:
            with open(data_file, "rb") as fh:
                old_chapters = pickle.load(file=fh)

            old_chapters.update(self._available_chapters)
            with open(data_file, "wb") as fh:
                pickle.dump(obj=old_chapters, file=fh)
        self._logger.info("Saved chapter list")

    def load_chapter_list(self):
        """
        Loads last saved chapter list, if found
        :return: Boolean
        """
        data_file = "{}.pkl".format(self._manga_name)
        if os.path.exists(data_file):
            with open(data_file, "rb") as fh:
                self._available_chapters = pickle.load(file=fh)
            self._logger.info("Loaded available chapter list")
            status = True
        else:
            self._logger.error("No chapter list found!")
            status = False
        return status

    def get_chapter(self, chapter_num, retry_count=3):
        """
        Gets chapter pages and saves them into a folder named cfater the chapter (CH-###)
        :param chapter_num: (int) chapter number [1:N] where N is the last available chapter
        :param retry_count: (int) Number of retries if failed to get chapter pages
        :return: None
        """
        chapter_url, chapter_page_count = self._available_chapters.get(chapter_num, (None, 0))

        if chapter_url:
            self._logger.info("Getting chapter {} pages..".format(chapter_num))
            chapter_dir_name = "CH-{:03d}".format(chapter_num)

            if not os.path.exists(chapter_dir_name):
                os.mkdir(chapter_dir_name)
                self._logger.info("Creating directory: {}".format(chapter_dir_name))
            else:
                self._logger.info("Chapter {} directory exists already!".format(chapter_num))
            os.chdir(chapter_dir_name)
            self._logger.debug("Moving into directory: {}".format(chapter_dir_name))

            for chapter_page in range(1, chapter_page_count+1):
                image_name = "{}-{:02d}.jpeg".format(chapter_num, chapter_page)
                if os.path.exists(image_name):
                    self._logger.debug("Chapter page {} exists already. Skipping to next page..".format(image_name))
                else:
                    self.get_chapter_page(chapter_num, chapter_page)

            os.chdir(self._target_dir)
            self._logger.info("Finished downloading chapter {}".format(chapter_num))

        else:
            self._logger.critical("Chapter {} isn't available in the chapter list!")
            self._logger.debug("Available chapters: {}".format(self._available_chapters.keys()))

    def get_chapter_page(self, chapter_num, page_num, retry_count=3):
        """
        Saves given chapter's page
        :param chapter_num: (int) chapter number
        :param page_num: (int) page number
        :param retry_count: (int) maximum number of retries if failed to get chapter page
        :return: None
        """
        chapter_url, chapter_pages_count = self._available_chapters.get(chapter_num, (None, 0))
        if not chapter_url:
            self._logger.critical("Chapter {} isn't available!".format(chapter_num))

        elif 0 >= page_num > chapter_pages_count:
            self._logger.critical("Chapter page {}-{} isn't available!".format(chapter_num, page_num))

        else:
            page_url = "{}/{}".format(chapter_url, page_num)
            status, page_source = self.get_page_source(page_url)

            if status:
                parsed_source = Soup(page_source, "lxml")
                image_obj = parsed_source.select("img#img")
                if image_obj:
                    image_url = image_obj[0].get("src")
                    image_name = "{:03d}-{}.jpeg".format(chapter_num, page_num)
                    self.save_image(image_url, image_name)
                else:
                    self._logger.critical("Failed to locate image {}-{}".format(chapter_num, page_num))

            else:
                if retry_count > 0:
                    self.get_chapter_page(chapter_num, page_num, retry_count=(retry_count-1))
                else:
                    self._logger.critical("Failed to get chapter page: {}-{}! Max retry exceeded!".format(chapter_num, page_num))

    def save_image(self, image_url, image_name):
        status, image_source = self.get_page_source(image_url)
        if status:
            with open(image_name, "wb") as fh:
                fh.write(image_source)
            self._logger.info("Saved image: {}".format(image_name))
        else:
            self._logger.error("Failed to download image: {}".format(image_name))

    def exception_handler(self, exception):
        pass

    def carry_command(self, command, *kwargs):
        pass

    def statistics(self):
        self._logger.info("[Statistics]:Total requests made: {}".format(self._total_req_count))
        self._logger.info("[Statistics]: Total bytes downloaded: {} MB".format(self._total_bytes/(1024*1024)))

    def grab_all_chapters(self):
        """
        Downloads all available chapters
        :return: None
        """
        self._logger.info("Trying to get all chapters..")

        status = self.load_chapter_list()

        if status:
            self._logger.info("Loaded chapter list, proceeding to download.")

        else:
            self.get_chapter_list(retry_count=3)
            self.save_chapter_list()
            self._logger.info("Saved chapter list, proceeding to download")

        for chapter_num in self._available_chapters.keys():
            self.get_chapter(chapter_num, retry_count=3)
        self._logger.info("Got all chapters successfully!")

    def check_last_chapter(self):
        pass


if __name__ == '__main__':

    # manga_url = r"https://www.mangareader.net/onepunch-man"
    # manga_url = r"https://www.mangareader.net/world-trigger"
    manga_url = r"https://www.mangareader.net/shingeki-no-kyojin"

    c = MangaReader(manga_url, target_dir=r"E:\Manga\Attack On Titan", wait_time=1)
    c.grab_all_chapters()
    c.statistics()

