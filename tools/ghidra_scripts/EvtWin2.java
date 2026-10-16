// EvtWin2: 自写字节扫描器 + COL/vftable 追踪 + 回调构造器反编译
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class EvtWin2 extends GhidraScript {

    List<Long> findPattern(byte[] pat) throws Exception {
        List<Long> hits = new ArrayList<>();
        int keep = pat.length - 1;
        for (MemoryBlock blk : currentProgram.getMemory().getBlocks()) {
            if (!blk.isInitialized()) {
                continue;
            }
            long start = blk.getStart().getOffset();
            long end = blk.getEnd().getOffset();
            int chunk = 1 << 22;
            byte[] buf = new byte[chunk];
            byte[] carry = new byte[0];
            long pos = start;
            outer:
            while (pos <= end) {
                int want = (int) Math.min(chunk, end - pos + 1);
                int got;
                try {
                    got = blk.getBytes(toAddr(pos), buf, 0, want);
                } catch (Exception e) {
                    break;
                }
                if (got <= 0) {
                    break;
                }
                byte[] data = new byte[carry.length + got];
                System.arraycopy(carry, 0, data, 0, carry.length);
                System.arraycopy(buf, 0, data, carry.length, got);
                long baseVa = pos - carry.length;
                for (int i = 0; i + pat.length <= data.length; i++) {
                    boolean ok = true;
                    for (int j = 0; j < pat.length; j++) {
                        if (data[i + j] != pat[j]) {
                            ok = false;
                            break;
                        }
                    }
                    if (ok) {
                        hits.add(baseVa + i);
                        if (hits.size() > 400) {
                            break outer;
                        }
                    }
                }
                if (got < want) {
                    break;
                }
                pos += got;
                int k = Math.min(keep, data.length);
                carry = Arrays.copyOfRange(data, data.length - k, data.length);
            }
        }
        return hits;
    }

    String readCStr(long va, int max) {
        StringBuilder sb = new StringBuilder();
        try {
            for (int i = 0; i < max; i++) {
                int b = getByte(toAddr(va + i)) & 0xff;
                if (b == 0) {
                    break;
                }
                sb.append((char) b);
            }
        } catch (Exception e) {
        }
        return sb.toString();
    }

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            println("  (no function @0x" + Long.toHexString(va) + ")");
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
                if (lines.length > cap) {
                    println("  ... (" + (lines.length - cap) + " more lines)");
                }
            } else {
                println("  (decompile failed)");
            }
            dec.dispose();
        } catch (Exception e) {
            println("  (decompile error " + e + ")");
        }
    }

    void allRefs(long va, String label) {
        println("==== ALL refs to " + label + " (0x" + Long.toHexString(va) + ") ====");
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
        }
    }

    void colHunt(long tdVA, String label) throws Exception {
        println("==== COL hunt: " + label + "  TD=0x" + Long.toHexString(tdVA) + " ====");
        long imgBase = currentProgram.getImageBase().getOffset();
        long rva = tdVA - imgBase;
        byte[] pat = new byte[4];
        for (int i = 0; i < 4; i++) {
            pat[i] = (byte) ((rva >>> (8 * i)) & 0xff);
        }
        List<Long> hits = findPattern(pat);
        println("  rva-pat hits=" + hits.size());
        Set<Long> cols = new LinkedHashSet<>();
        for (long h : hits) {
            long colVA = h - 0xC;
            try {
                if (getInt(toAddr(colVA)) != 1) {
                    continue;
                }
                int tdRva = getInt(toAddr(colVA + 0xC));
                if ((tdRva & 0xffffffffL) != rva) {
                    continue;
                }
                cols.add(colVA);
            } catch (Exception e) {
            }
        }
        println("  valid COLs: " + cols.size());
        for (long colVA : cols) {
            println("  COL @0x" + Long.toHexString(colVA));
            byte[] p8 = new byte[8];
            for (int i = 0; i < 8; i++) {
                p8[i] = (byte) ((colVA >>> (8 * i)) & 0xff);
            }
            List<Long> refs = findPattern(p8);
            println("    vftable-slot refs: " + refs.size());
            for (long r : refs) {
                long vt = r + 8;
                println("    vftable @0x" + Long.toHexString(vt));
                for (int k = 0; k < 6; k++) {
                    long fn = getLong(toAddr(vt + 8L * k));
                    if (fn < 0x140000000L || fn > 0x150000000L) {
                        break;
                    }
                    Function f = getFunctionContaining(toAddr(fn));
                    println("      [" + k + "] 0x" + Long.toHexString(fn) + "  " + (f != null ? f.getName() : "?"));
                }
                Set<Long> fseen = new LinkedHashSet<>();
                List<Long> faddrs = new ArrayList<>();
                for (Reference vr : getReferencesTo(toAddr(vt))) {
                    Function vf = getFunctionContaining(vr.getFromAddress());
                    long fe = vf != null ? vf.getEntryPoint().getOffset() : 0;
                    println("      ref " + vr.getReferenceType() + " from " + vr.getFromAddress()
                            + " in " + (vf != null ? vf.getName() + "@0x" + Long.toHexString(fe) : "?"));
                    if (vf != null && fseen.add(fe)) {
                        faddrs.add(fe);
                    }
                }
                int maxDec = 2;
                for (long fe : faddrs) {
                    if (maxDec-- <= 0) {
                        break;
                    }
                    decompileFn(fe, 120);
                }
            }
        }
    }

    @Override
    public void run() throws Exception {
        println("imageBase=0x" + Long.toHexString(currentProgram.getImageBase().getOffset()));

        // 0) scanner self-test: 已知字符串
        List<Long> st = findPattern("Setup@CEventWindow@@".getBytes("US-ASCII"));
        println("self-test 'Setup@CEventWindow@@' hits=" + st.size());
        for (long h : st) {
            println("  @0x" + Long.toHexString(h));
        }

        // 1) 所有 Setup@CEventWindow 相关 RTTI 名（lambda_1 / bind_t / ...）
        List<Long> lam = findPattern("?1??Setup@CEventWindow@@UEAAXXZ@".getBytes("US-ASCII"));
        println("lambda-mangling hits=" + lam.size());
        for (long h : lam) {
            println("  @0x" + Long.toHexString(h) + " ctx: " + readCStr(h - 60, 150));
        }


        // 2) CEventWindow 类名单独搜
        List<Long> cw = findPattern(".?AVCEventWindow@@".getBytes("US-ASCII"));
        println("'.?AVCEventWindow@@' exact hits=" + cw.size());
        for (long h : cw) {
            println("  @0x" + Long.toHexString(h) + " : " + readCStr(h, 150));
        }

        // 3) COL 追踪
        colHunt(0x1428c59a0L, "lambda_1 TD");
        colHunt(0x1428c59e0L, "bind_t TD");
        if (!cw.isEmpty()) {
            colHunt(cw.get(0) - 0x10, "CEventWindow class TD");
        }

        // 4) 事件选项构建链的调用者
        allRefs(0x14107a180L, "FUN_14107a180 option-entry builder");
        allRefs(0x1410793a0L, "FUN_1410793a0 window chunk");
        allRefs(0x141291c80L, "FUN_141291c80 telemetry wrapper");
        allRefs(0x141291ce0L, "FUN_141291ce0 telemetry wrapper");

        // 5) 回调构造器
        decompileFn(0x1407b5a10L, 150);

        println("==== done ====");
    }
}
