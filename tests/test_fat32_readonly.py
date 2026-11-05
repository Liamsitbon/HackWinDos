"""Read fragmented evidence from a sparse FAT32 fixture; reject invalid chains."""
from pathlib import Path
import struct
import tempfile
import unittest
from tools.fat32_readonly import Fat32Reader


class Fat32ReadOnlyTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'fat32.img'
        self.sector=512;self.reserved=32;self.fatsize=512
        self.data=1056;self.clusters=65525;self.size=(self.data+self.clusters)*512
        with self.path.open('wb') as f:f.truncate(self.size)
        b=bytearray(512);b[:3]=b'\xeb\x58\x90';b[510:]=b'\x55\xaa'
        struct.pack_into('<H',b,11,512);b[13]=1;struct.pack_into('<H',b,14,32);b[16]=2
        struct.pack_into('<I',b,32,self.data+self.clusters);struct.pack_into('<I',b,36,512)
        struct.pack_into('<I',b,44,2);self.put(0,b)
        for i in range(2):
            for cluster,value in [(0,0x0ffffff8),(1,0x0fffffff),(2,0x0fffffff),
                                  (3,7),(4,0x0fffffff),(5,0x0fffffff),(7,0x0fffffff)]:
                self.fat(i,cluster,value)
        self.put(self.offset(2),self.entry(b'M1N1       ',0x10,5,0))
        self.put(self.offset(5),self.entry(b'BOOT    BIN',0x20,3,700)+
                 self.entry(b'J413UEFILOG',0x20,4,18))
        self.put(self.offset(3),b'A'*512);self.put(self.offset(7),b'B'*188)
        self.put(self.offset(4),b'USB test: Success\n')

    def put(self,offset,data):
        with self.path.open('r+b') as f:f.seek(offset);f.write(data)

    def offset(self,c):return (self.data+c-2)*512

    def fat(self,copy,c,value):self.put((32+copy*512)*512+c*4,struct.pack('<I',value))

    @staticmethod
    def entry(name,attr,cluster,size):
        b=bytearray(32);b[:11]=name;b[11]=attr
        struct.pack_into('<H',b,20,cluster>>16);struct.pack_into('<H',b,26,cluster&65535)
        struct.pack_into('<I',b,28,size);return b

    def read(self,path='m1n1/boot.bin',limit=8192,block=512):
        before=self.path.stat().st_mtime_ns
        with self.path.open('rb',buffering=0) as f:
            result=Fat32Reader(f,self.size,block).read_file(path,limit)
        self.assertEqual(self.path.stat().st_mtime_ns,before)
        return result

    def test_fragmented_file_case_insensitive_short_names_and_no_writes(self):
        self.assertEqual(self.read(),b'A'*512+b'B'*188)
        self.assertEqual(self.read('M1N1/J413UEFI.LOG'),b'USB test: Success\n')

    def test_raw_device_reads_are_aligned_even_for_fat_entries(self):
        # Use a 4096-aligned measured partition while BPB sectors remain 512.
        aligned=(self.size+4095)//4096*4096
        with self.path.open('r+b') as f:f.truncate(aligned)
        class Aligned:
            def __init__(self,f):self.f=f
            def seek(self,n):self.assert_aligned(n);self.f.seek(n)
            def read(self,n):self.assert_aligned(n);return self.f.read(n)
            @staticmethod
            def assert_aligned(n):assert n%4096==0
        with self.path.open('rb',buffering=0) as f:
            reader=Fat32Reader(Aligned(f),aligned,4096)
            self.assertEqual(reader.read_file('m1n1/boot.bin',1024),b'A'*512+b'B'*188)

    def test_mirror_disagreement_and_invalid_file_cluster_are_rejected(self):
        self.fat(1,3,8)
        with self.assertRaisesRegex(ValueError,'disagrees'):self.read()
        self.fat(0,3,0);self.fat(1,3,0)
        with self.assertRaisesRegex(ValueError,'Invalid'):self.read()

    def test_active_fat_selection_does_not_guess_from_a_bad_inactive_copy(self):
        self.put(40,struct.pack('<H',0x81));self.fat(0,3,0)
        self.assertEqual(self.read(),b'A'*512+b'B'*188)

    def test_cycle_truncation_size_and_bad_geometry_fail_closed(self):
        self.fat(0,3,3);self.fat(1,3,3)
        with self.assertRaisesRegex(ValueError,'Cyclic'):self.read()
        self.fat(0,3,0x0fffffff);self.fat(1,3,0x0fffffff)
        with self.assertRaisesRegex(ValueError,'truncated'):self.read()
        with self.assertRaisesRegex(ValueError,'size'):self.read(limit=10)
        self.put(32,struct.pack('<I',0xffffffff))
        with self.assertRaisesRegex(ValueError,'geometry'):self.read()

    def test_duplicate_name_and_path_traversal_are_rejected(self):
        duplicate=self.entry(b'BOOT    BIN',0x20,3,700)
        self.put(self.offset(5)+64,duplicate)
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.read()
        with self.assertRaisesRegex(ValueError,'fixed directory'):self.read('../m1n1/boot.bin')
