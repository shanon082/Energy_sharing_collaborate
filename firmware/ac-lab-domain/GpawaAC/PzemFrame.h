#pragma once
#include <stdint.h>
#include <stddef.h>
namespace pz {
inline uint16_t crc(const uint8_t* b,size_t n){uint16_t c=65535;while(n--){c^=*b++;for(int j=0;j<8;j++)c=(c&1)?(c>>1)^0xa001:c>>1;}return c;}
struct Reading {uint32_t mv,ma,mw,wh;};
inline bool decode(const uint8_t* b,size_t n,uint8_t addr,Reading& out){
 if(n!=25||b[0]!=addr||b[1]!=4||b[2]!=20||crc(b,23)!=(b[23]|(uint16_t(b[24])<<8)))return false;
 auto reg=[&](int i)->uint32_t{return (uint32_t(b[3+i*2])<<8)|b[4+i*2];};
 out={reg(0)*100,(reg(2)<<16)|reg(1),((reg(4)<<16)|reg(3))*100,(reg(6)<<16)|reg(5)};
 return out.mv>=80000 && out.mv<=260000 && reg(7)>=450 && reg(7)<=650 && reg(8)<=100;
}
}
