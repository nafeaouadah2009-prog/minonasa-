import React, { useEffect, useRef } from 'react';
import { View, Animated, StyleSheet, Easing } from 'react-native';
import colors from '../theme/colors';

// العنصر المميز (Signature Element) للتطبيق:
// خط فاصل بسيط يتنفس ببطء (يتوسع وينكمش) بدلاً من أي زخرفة صاخبة،
// يرمز لإيقاع الذكر والتنفس الهادئ. يظهر بين الأقسام الرئيسية فقط.

export default function BreathingDivider() {
  const scale = useRef(new Animated.Value(0.4)).current;
  const opacity = useRef(new Animated.Value(0.35)).current;

  useEffect(() => {
    const breathe = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(scale, {
            toValue: 1,
            duration: 2600,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(opacity, {
            toValue: 0.9,
            duration: 2600,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
        Animated.parallel([
          Animated.timing(scale, {
            toValue: 0.4,
            duration: 2600,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(opacity, {
            toValue: 0.35,
            duration: 2600,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
      ])
    );
    breathe.start();
    return () => breathe.stop();
  }, [scale, opacity]);

  return (
    <View style={styles.wrapper}>
      <Animated.View
        style={[
          styles.dot,
          { opacity, transform: [{ scaleX: scale }] },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    width: '100%',
    alignItems: 'center',
    paddingVertical: 18,
  },
  dot: {
    width: 90,
    height: 1.5,
    backgroundColor: colors.accent,
    borderRadius: 2,
  },
});
