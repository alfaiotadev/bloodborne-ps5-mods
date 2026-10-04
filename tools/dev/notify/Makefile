PS5_PAYLOAD_SDK ?= /opt/ps5-payload-sdk
include $(PS5_PAYLOAD_SDK)/toolchain/prospero.mk
notify.elf: notify.cpp
	$(CXX) -Wall -O2 -o $@ $^
clean:
	rm -f notify.elf
