.PHONY: all test clean

build:
	cd cacti && make clean && make
	chmod 775 cacti/cacti